const STOCK_REPLY = "Hello! Nice day for fishing, aint it?";

export function reply(): Promise<string> {
  return Promise.resolve(STOCK_REPLY);
}
