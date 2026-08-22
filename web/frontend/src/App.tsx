import { useState } from "react";
import { createUpload, getResults, pollJob, startJob, uploadFile } from "./api";
import DocsPanel from "./DocsPanel";
import FilePanel from "./FilePanel";
import ResultsView from "./ResultsView";
import SettingsPanel from "./SettingsPanel";
import { DEFAULT_SETTINGS, type BatchResult, type PipelineSettings } from "./types";

export default function App() {
  const [view, setView] = useState<"analyze" | "docs">("analyze");
  const [fasta, setFasta] = useState<File | null>(null);
  const [fastqs, setFastqs] = useState<File[]>([]);
  const [combineFastqs, setCombineFastqs] = useState(false);
  const [settings, setSettings] = useState<PipelineSettings>(DEFAULT_SETTINGS);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState(
    "Select a reference FASTA and one or more FASTQ files, then click Run analysis.",
  );
  const [result, setResult] = useState<BatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!fasta || fastqs.length === 0) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      setStatus("Uploading files…");
      const uploadId = await createUpload();
      await uploadFile(uploadId, fasta);
      for (const file of fastqs) {
        setStatus(`Uploading ${file.name}…`);
        await uploadFile(uploadId, file);
      }
      setStatus(combineFastqs ? "Combining FASTQs…" : "Queued…");
      const job = await startJob(
        uploadId,
        fasta.name,
        fastqs.map((f) => f.name),
        settings,
        combineFastqs && fastqs.length > 1,
      );
      const done = await pollJob(job.id, (s) => {
        if (s.status === "queued") setStatus("Queued…");
        else if (s.progress) {
          if (s.progress.i === 0) setStatus("Combining FASTQs…");
          else {
            setStatus(
              `Processing sample ${s.progress.i} of ${s.progress.n}: ${s.progress.sample}`,
            );
          }
        } else if (s.status === "running") setStatus("Running…");
      });
      if (done.status === "failed") {
        setError(done.error ?? "Run failed.");
        setStatus(done.is_validation ? "FASTA validation failed." : "Run failed.");
        return;
      }
      const batch = await getResults(done.id);
      setResult(batch);
      setStatus(
        `Done. ${batch.samples.length} sample(s) · ${batch.n_assigned.toLocaleString()} assigned reads · ${batch.n_unassigned.toLocaleString()} unassigned`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("Run failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <header className="app-header">
        <h1>CRISPR Amplicon Editing Efficiency</h1>
        <nav className="app-nav">
          <button
            type="button"
            className={view === "analyze" ? "active" : ""}
            onClick={() => setView("analyze")}
          >
            Analysis
          </button>
          <button
            type="button"
            className={view === "docs" ? "active" : ""}
            onClick={() => setView("docs")}
          >
            How it works
          </button>
        </nav>
      </header>
      {view === "docs" ? (
        <DocsPanel />
      ) : (
        <>
          <FilePanel
            fasta={fasta}
            fastqs={fastqs}
            running={running}
            combineFastqs={combineFastqs}
            onFasta={setFasta}
            onFastqs={setFastqs}
            onCombineFastqs={setCombineFastqs}
            onRun={run}
          />
          <SettingsPanel value={settings} disabled={running} onChange={setSettings} />
          {running && <progress className="run-progress" />}
          <p className="status">{status}</p>
          {error && <pre className="error">{error}</pre>}
          <ResultsView result={result} />
        </>
      )}
    </>
  );
}
