import { useState } from 'react';
import { BookOpen } from 'lucide-react';
import type { StrategyGuideData } from './types';
import { strategyGuides } from './strategyGuides';

type Props = {
  onBack: () => void;
};

export default function StrategyGuide({ onBack }: Props) {
  const [selectedId, setSelectedId] = useState(strategyGuides[0]?.id ?? '');
  const selected = strategyGuides.find((s) => s.id === selectedId);

  return (
    <div className="strategy-guide">
      <aside className="guide-sidebar">
        <div className="guide-sidebar-header">
          <BookOpen size={20} />
          <h2>策略库</h2>
        </div>
        <nav className="guide-nav">
          {strategyGuides.map((s) => (
            <button
              key={s.id}
              className={`guide-nav-item${s.id === selectedId ? ' active' : ''}`}
              onClick={() => setSelectedId(s.id)}
            >
              {s.name}
            </button>
          ))}
        </nav>
        <button className="guide-back-btn" onClick={onBack}>
          &larr; 返回回测
        </button>
      </aside>

      <section className="guide-content">
        {selected ? (
          <>
            <header className="guide-header">
              <h1>{selected.name}</h1>
              <p className="guide-desc">{selected.description}</p>
              <span className="guide-scenario">{selected.applicableScenarios}</span>
            </header>

            <section className="guide-section">
              <h2>{selected.principle.title}</h2>
              {selected.principle.content.split('\n\n').map((para, i) => (
                <p key={i}>{para.trim()}</p>
              ))}
            </section>

            <section className="guide-section">
              <h2>参数详解</h2>
              <div className="guide-params-table-wrapper">
                <table className="guide-params-table">
                  <thead>
                    <tr>
                      <th>参数名</th>
                      <th>含义</th>
                      <th>推荐值</th>
                      <th>调整建议</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.parameters.map((p) => (
                      <tr key={p.name}>
                        <td><code>{p.name}</code><br /><span className="param-label">{p.label}</span></td>
                        <td>{p.meaning}</td>
                        <td className="param-value">{p.recommendedValue}</td>
                        <td>{p.adjustmentTips}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="guide-section guide-chars">
              <h2>交易特征</h2>
              <div className="chars-grid">
                <div className="char-card">
                  <span className="char-label">交易频率</span>
                  <strong>{selected.characteristics.tradingFrequency}</strong>
                </div>
                <div className="char-card">
                  <span className="char-label">持仓周期</span>
                  <strong>{selected.characteristics.holdingPeriod}</strong>
                </div>
                <div className="char-card">
                  <span className="char-label">适用股票</span>
                  <strong>{selected.characteristics.applicableStocks}</strong>
                </div>
                <div className="char-card">
                  <span className="char-label">风险等级</span>
                  <strong>{selected.characteristics.riskLevel}</strong>
                </div>
              </div>
            </section>
          </>
        ) : (
          <div className="guide-empty">未找到策略说明</div>
        )}
      </section>
    </div>
  );
}
