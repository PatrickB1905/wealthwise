import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';

import { useInstrumentSearch } from './useInstrumentSearch';
import * as marketDataClient from '../api/marketDataClient';

jest.mock('../api/marketDataClient', () => ({
  searchInstruments: jest.fn(),
}));

const mockedSearchInstruments = marketDataClient.searchInstruments as jest.MockedFunction<
  typeof marketDataClient.searchInstruments
>;

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

function HookHarness({
  query,
  enabled = true,
}: {
  query: string;
  enabled?: boolean;
}) {
  const result = useInstrumentSearch(query, { enabled });

  return (
    <div>
      <div data-testid="status">
        {result.isFetching ? 'fetching' : result.isSuccess ? 'success' : 'idle'}
      </div>
      <div data-testid="count">{String(result.data?.length ?? 0)}</div>
    </div>
  );
}

describe('useInstrumentSearch', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    act(() => {
      jest.runOnlyPendingTimers();
    });
    jest.useRealTimers();
  });

  it('does not search when the query is shorter than 2 characters', async () => {
    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <HookHarness query="A" />
      </QueryClientProvider>,
    );

    act(() => {
      jest.advanceTimersByTime(350);
    });

    await waitFor(() => {
      expect(screen.getByTestId('count')).toHaveTextContent('0');
    });

    expect(mockedSearchInstruments).not.toHaveBeenCalled();
  });

  it('does not search when disabled', async () => {
    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <HookHarness query="AAPL" enabled={false} />
      </QueryClientProvider>,
    );

    act(() => {
      jest.advanceTimersByTime(350);
    });

    await waitFor(() => {
      expect(screen.getByTestId('count')).toHaveTextContent('0');
    });

    expect(mockedSearchInstruments).not.toHaveBeenCalled();
  });

  it('debounces when the query changes from empty to a searchable value', async () => {
    mockedSearchInstruments.mockResolvedValue([
      {
        symbol: 'AAPL',
        name: 'Apple Inc.',
        exchange: 'NASDAQ',
        assetType: 'EQUITY',
        currency: 'USD',
        logoUrl: 'https://logo.example/aapl.png',
      },
    ]);

    const queryClient = createTestQueryClient();

    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <HookHarness query="" />
      </QueryClientProvider>,
    );

    expect(mockedSearchInstruments).not.toHaveBeenCalled();

    rerender(
      <QueryClientProvider client={queryClient}>
        <HookHarness query="apple" />
      </QueryClientProvider>,
    );

    act(() => {
      jest.advanceTimersByTime(299);
    });
    expect(mockedSearchInstruments).not.toHaveBeenCalled();

    act(() => {
      jest.advanceTimersByTime(1);
    });

    await waitFor(() => {
      expect(mockedSearchInstruments).toHaveBeenCalledWith('apple');
    });

    await waitFor(() => {
      expect(screen.getByTestId('count')).toHaveTextContent('1');
    });
  });
});