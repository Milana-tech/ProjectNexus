import { render, screen } from "@testing-library/react";
import { CustomTooltip } from "./Dashboard";

describe("CustomTooltip anomaly rendering", () => {
  it("renders anomaly timestamp, value, and score when all required fields exist", () => {
    const label = "2026-02-17T10:00:00.000Z";
    render(
      <CustomTooltip
        active
        label={label}
        unit="C"
        payload={[
          {
            dataKey: "value",
            name: "Temperature",
            value: 21.5,
            color: "#2563eb",
            payload: {
              isAnomaly: true,
              anomalyScore: 2.5,
            },
          },
        ]}
      />
    );

    expect(screen.getByTestId("metric-tooltip")).toBeInTheDocument();
    expect(screen.getByTestId("anomaly-tooltip-details")).toBeInTheDocument();
    expect(screen.getByText("Anomaly Event")).toBeInTheDocument();
    expect(screen.getByText("Timestamp")).toBeInTheDocument();
    expect(screen.getByText("Value")).toBeInTheDocument();
    expect(screen.getByText("Score")).toBeInTheDocument();
    expect(screen.getByText("2.5")).toBeInTheDocument();
  });

  it("fails gracefully when required anomaly fields are missing", () => {
    render(
      <CustomTooltip
        active
        label="not-a-date"
        unit="C"
        payload={[
          {
            dataKey: "value",
            name: "Temperature",
            value: 20.1,
            color: "#2563eb",
            payload: {
              isAnomaly: true,
              anomalyScore: null,
            },
          },
        ]}
      />
    );

    expect(screen.getByTestId("metric-tooltip")).toBeInTheDocument();
    expect(screen.queryByTestId("anomaly-tooltip-details")).not.toBeInTheDocument();
    expect(screen.getByText("Unknown time")).toBeInTheDocument();
    expect(screen.getByText("20.1 C")).toBeInTheDocument();
  });

  it("applies positioning styles for tooltip layout", () => {
    render(
      <CustomTooltip
        active
        label="2026-02-17T10:00:00.000Z"
        unit="C"
        payload={[
          {
            dataKey: "value",
            name: "Temperature",
            value: 18.7,
            color: "#2563eb",
            payload: {
              isAnomaly: true,
              anomalyScore: 1.9,
            },
          },
        ]}
      />
    );

    const root = screen.getByTestId("metric-tooltip");
    const anomalyDetails = screen.getByTestId("anomaly-tooltip-details");
    expect(root).toHaveStyle({ position: "relative" });
    expect(anomalyDetails).toHaveStyle({ marginTop: "8px" });
  });
});
