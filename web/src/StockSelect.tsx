import { useState, useRef, useEffect } from 'react';
import { ChevronDown, AlertCircle } from 'lucide-react';
import { getStocks } from './api';

interface Stock {
  code: string;
  name: string;
}

interface StockSelectProps {
  value: string;
  onChange: (code: string) => void;
}

export function StockSelect({ value, onChange }: StockSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredStocks, setFilteredStocks] = useState<Stock[]>([]);
  const [allStocks, setAllStocks] = useState<Stock[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load stocks on component mount
  useEffect(() => {
    const loadStocks = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const stocks = await getStocks();
        setAllStocks(stocks);
        setFilteredStocks(stocks);
      } catch (err) {
        setError('Failed to load stocks');
        console.error('Error loading stocks:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadStocks();
  }, []);

  // Update selected stock when value changes
  useEffect(() => {
    const stock = allStocks.find(s => s.code === value);
    setSelectedStock(stock || null);
  }, [value, allStocks]);

  // Filter stocks based on search query
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredStocks(allStocks);
      return;
    }

    const normalizedQuery = searchQuery.trim().toLowerCase();
    setFilteredStocks(
      allStocks.filter(
        (stock) =>
          stock.code.includes(normalizedQuery) || stock.name.toLowerCase().includes(normalizedQuery)
      )
    );
  }, [searchQuery, allStocks]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const displayLabel = selectedStock ? `${selectedStock.code} - ${selectedStock.name}` : '选择股票';

  return (
    <div className="stock-select-container" ref={containerRef}>
      <button
        type="button"
        className="stock-select-button"
        onClick={() => {
          setIsOpen(!isOpen);
          if (!isOpen) {
            setTimeout(() => inputRef.current?.focus(), 0);
          }
        }}
      >
        <span className="stock-select-label">{displayLabel}</span>
        <ChevronDown size={16} className={`chevron ${isOpen ? 'open' : ''}`} />
      </button>

      {isOpen && (
        <div className="stock-select-dropdown">
          <input
            ref={inputRef}
            type="text"
            className="stock-select-search"
            placeholder="搜索代码或名称..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
            disabled={isLoading}
          />
          <div className="stock-select-list">
            {error ? (
              <div className="stock-select-error">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            ) : isLoading ? (
              <div className="stock-select-loading">
                <div className="spinner"></div>
                <span>加载股票列表中...</span>
              </div>
            ) : filteredStocks.length > 0 ? (
              filteredStocks.map((stock) => (
                <button
                  key={stock.code}
                  type="button"
                  className={`stock-select-item ${value === stock.code ? 'selected' : ''}`}
                  onClick={() => {
                    onChange(stock.code);
                    setIsOpen(false);
                    setSearchQuery('');
                  }}
                >
                  <span className="stock-code">{stock.code}</span>
                  <span className="stock-name">{stock.name}</span>
                </button>
              ))
            ) : (
              <div className="stock-select-empty">未找到匹配的股票</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
