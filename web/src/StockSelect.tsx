import { useState, useRef, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import { STOCKS, searchStocks } from './stocks';

interface StockSelectProps {
  value: string;
  onChange: (code: string) => void;
}

export function StockSelect({ value, onChange }: StockSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredStocks, setFilteredStocks] = useState(STOCKS);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setFilteredStocks(searchStocks(searchQuery));
  }, [searchQuery]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedStock = STOCKS.find(s => s.code === value);
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
          />
          <div className="stock-select-list">
            {filteredStocks.length > 0 ? (
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
