import { useCallback, useRef } from "react";

const FASTA_RE = /\.(fasta|fa|fna|fas|txt)$/i;
const FASTQ_RE = /\.(fastq|fq)(\.gz)?$/i;

type Props = {
  fasta: File | null;
  fastqs: File[];
  running: boolean;
  onFasta: (file: File | null) => void;
  onFastqs: (files: File[]) => void;
  onRun: () => void;
};

function classify(file: File): "fasta" | "fastq" | null {
  if (FASTQ_RE.test(file.name)) return "fastq";
  if (FASTA_RE.test(file.name)) return "fasta";
  return null;
}

export default function FilePanel({
  fasta,
  fastqs,
  running,
  onFasta,
  onFastqs,
  onRun,
}: Props) {
  const fastaRef = useRef<HTMLInputElement>(null);
  const fastqRef = useRef<HTMLInputElement>(null);
  const canRun = Boolean(fasta) && fastqs.length > 0 && !running;

  const addFiles = useCallback(
    (list: FileList | File[]) => {
      const incoming = Array.from(list);
      const nextFastq = [...fastqs];
      const have = new Set(nextFastq.map((f) => f.name));
      for (const file of incoming) {
        const kind = classify(file);
        if (kind === "fasta") onFasta(file);
        else if (kind === "fastq" && !have.has(file.name)) {
          nextFastq.push(file);
          have.add(file.name);
        }
      }
      onFastqs(nextFastq);
    },
    [fastqs, onFasta, onFastqs],
  );

  return (
    <section
      className="panel"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        addFiles(e.dataTransfer.files);
      }}
    >
      <label className="row">
        <span>Reference FASTA</span>
        <input
          className="grow"
          readOnly
          value={fasta?.name ?? ""}
          placeholder="Amplicon + guide FASTA…"
        />
        <button type="button" disabled={running} onClick={() => fastaRef.current?.click()}>
          Browse…
        </button>
        <input
          ref={fastaRef}
          type="file"
          hidden
          accept=".fasta,.fa,.fna,.fas,.txt"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFasta(f);
            e.target.value = "";
          }}
        />
      </label>

      <div className="label">FASTQ samples</div>
      <ul className="file-list">
        {fastqs.map((f) => (
          <li key={f.name}>
            <span>{f.name}</span>
            <button
              type="button"
              disabled={running}
              onClick={() => onFastqs(fastqs.filter((x) => x.name !== f.name))}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      <div className="row">
        <button type="button" disabled={running} onClick={() => fastqRef.current?.click()}>
          Add FASTQ…
        </button>
        <button type="button" disabled={running || fastqs.length === 0} onClick={() => onFastqs([])}>
          Clear
        </button>
        <input
          ref={fastqRef}
          type="file"
          hidden
          multiple
          accept=".fastq,.fq,.fastq.gz,.fq.gz"
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <span className="hint">Drop FASTA/FASTQ here. Select multiple FASTQ files for a batch.</span>
        <button type="button" className="run" disabled={!canRun} onClick={onRun}>
          {running ? "Running…" : "Run analysis"}
        </button>
      </div>
    </section>
  );
}
