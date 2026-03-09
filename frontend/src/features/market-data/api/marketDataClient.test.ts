const mockedGet = jest.fn();

jest.mock('@shared/lib/http', () => ({
  createHttpClient: jest.fn(() => ({
    get: mockedGet,
  })),
}));

import { searchInstruments } from './marketDataClient';

describe('marketDataClient.searchInstruments', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns an empty array when the query is shorter than 2 characters', async () => {
    await expect(searchInstruments('A')).resolves.toEqual([]);
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it('trims the query and calls the instrument search endpoint with the expected params', async () => {
    mockedGet.mockResolvedValue({
      data: [
        {
          symbol: 'AAPL',
          name: 'Apple Inc.',
          exchange: 'NASDAQ',
          assetType: 'EQUITY',
          currency: 'USD',
          logoUrl: 'https://logo.example/aapl.png',
        },
      ],
    });

    const result = await searchInstruments('  apple  ');

    expect(mockedGet).toHaveBeenCalledWith('/instruments/search', {
      params: { q: 'apple', limit: 10 },
    });

    expect(result).toEqual([
      {
        symbol: 'AAPL',
        name: 'Apple Inc.',
        exchange: 'NASDAQ',
        assetType: 'EQUITY',
        currency: 'USD',
        logoUrl: 'https://logo.example/aapl.png',
      },
    ]);
  });
});