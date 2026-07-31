// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

it("renders a non-usable launch-context state at the Treatment Plan root", async () => {
  document.body.innerHTML = '<div id="root"></div>';
  window.history.replaceState({}, "", "/modules/treatment-plan");
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);

  await import("./main");

  expect(await screen.findByRole("heading", { name: "Select a Treatment Plan before opening review" })).toBeTruthy();
  expect(screen.getByText(/does not select a plan/)).toBeTruthy();
  expect(fetcher).not.toHaveBeenCalled();
});
