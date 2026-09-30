/** Mock services wait a little, so loading states are exercised like with a real API. */
export function simulateLatency(ms = 250): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
