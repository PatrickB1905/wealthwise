import type { InstrumentSearchResult } from '@features/market-data/api/marketDataClient';

export function formatInstrumentInputValue(option: InstrumentSearchResult): string {
  return `${option.symbol} - ${option.name}`;
}