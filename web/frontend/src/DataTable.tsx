import { useState } from "react";

type Props = {
  columns: string[];
  rows: Record<string, unknown>[];
  filename: string;
  onSelect?: (row: Record<string, unknown> | null) => void;
};

function csvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = String(value);
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function exportCsv(filename: string, columns: string[], rows: Record<string, unknown>[]) {
  const lines = [
    columns.join(","),
    ...rows.map((row) => columns.map((c) => csvCell(row[c])).join(",")),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function DataTable({ columns, rows, filename, onSelect }: Props) {
  const [needle, setNeedle] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const [selected, setSelected] = useState<number | null>(null);

  const filtered = rows.filter((row) => {
    if (!needle) return true;
    const n = needle.toLowerCase();
    return columns.some((c) => String(row[c] ?? "").toLowerCase().includes(n));
  });

  const sorted = sort
    ? [...filtered].sort((a, b) => {
        const av = a[sort.key];
        const bv = b[sort.key];
        if (typeof av === "number" && typeof bv === "number") return (av - bv) * sort.dir;
        return String(av ?? "").localeCompare(String(bv ?? "")) * sort.dir;
      })
    : filtered;

  return (
    <div className="table-tab">
      <div className="row">
        <span>Filter</span>
        <input
          className="grow"
          placeholder="Filter…"
          value={needle}
          onChange={(e) => {
            setNeedle(e.target.value);
            setSelected(null);
            onSelect?.(null);
          }}
        />
        <button type="button" onClick={() => exportCsv(filename, columns, sorted)}>
          Export CSV
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c}
                  onClick={() =>
                    setSort((s) =>
                      s?.key === c ? { key: c, dir: s.dir === 1 ? -1 : 1 } : { key: c, dir: 1 },
                    )
                  }
                >
                  {c}
                  {sort?.key === c ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr
                key={i}
                className={selected === i ? "selected" : ""}
                onClick={() => {
                  const next = selected === i ? null : i;
                  setSelected(next);
                  onSelect?.(next === null ? null : sorted[next]);
                }}
              >
                {columns.map((c) => (
                  <td key={c}>{formatCell(row[c])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}
