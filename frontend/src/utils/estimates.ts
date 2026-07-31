export function formatEstimate(minutes: number | null): string {
  return minutes === null ? "Estimate needed" : `${minutes} min`;
}

export function formatEstimateLong(minutes: number | null): string {
  return minutes === null ? "Estimate needed" : `${minutes} minutes`;
}
