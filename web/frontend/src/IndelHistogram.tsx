import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from "chart.js";
import { Bar } from "react-chartjs-2";

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend);

type Props = {
  sizes: number[];
  title?: string;
};

export default function IndelHistogram({ sizes, title }: Props) {
  if (!sizes.length) {
    return (
      <p className="hint">
        {title ?? "No indel size calls for this selection."}
      </p>
    );
  }
  const counts = new Map<number, number>();
  for (const z of sizes) counts.set(z, (counts.get(z) ?? 0) + 1);
  const labels = [...counts.keys()].sort((a, b) => a - b);
  return (
    <div className="histogram">
      {title ? <p className="hint">{title}</p> : null}
      <Bar
        data={{
          labels: labels.map(String),
          datasets: [
            {
              label: "Reads",
              data: labels.map((z) => counts.get(z) ?? 0),
              backgroundColor: "#1f6feb",
            },
          ],
        }}
        options={{
          maintainAspectRatio: false,
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              title: {
                display: true,
                text: "Net indel size (bp)",
                color: "#333",
              },
              ticks: { color: "#444", maxRotation: 0, autoSkip: true },
              grid: { color: "rgba(0,0,0,0.06)" },
            },
            y: {
              title: { display: true, text: "Reads", color: "#333" },
              ticks: { color: "#444", precision: 0 },
              beginAtZero: true,
              grid: { color: "rgba(0,0,0,0.08)" },
            },
          },
        }}
      />
    </div>
  );
}
