import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BookOpen } from 'lucide-react';
import { strategyGuides } from './strategyGuides';

type Props = {
  onBack: () => void;
};

export default function StrategyGuide({ onBack }: Props) {
  const { t } = useTranslation();
  const [selectedId, setSelectedId] = useState(strategyGuides[0]?.id ?? '');
  const selected = strategyGuides.find((s) => s.id === selectedId);

  return (
    <div className="strategy-guide">
      <aside className="guide-sidebar">
        <div className="guide-sidebar-header">
          <BookOpen size={20} />
          <h2>{t('strategyGuide.title')}</h2>
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
          &larr; {t('strategyGuide.back')}
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
              <h2>{t('strategyGuide.params')}</h2>
              <div className="guide-params-table-wrapper">
                <table className="guide-params-table">
                  <thead>
                    <tr>
                      <th>{t('strategyGuide.paramName')}</th>
                      <th>{t('strategyGuide.paramMeaning')}</th>
                      <th>{t('strategyGuide.paramRecommended')}</th>
                      <th>{t('strategyGuide.paramTips')}</th>
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
              <h2>{t('strategyGuide.chars')}</h2>
              <div className="guide-chars-grid">
                <div className="guide-char-card">
                  <span className="guide-char-label">{t('strategyGuide.tradingFrequency')}</span>
                  <strong>{selected.characteristics.tradingFrequency}</strong>
                </div>
                <div className="guide-char-card">
                  <span className="guide-char-label">{t('strategyGuide.holdingPeriod')}</span>
                  <strong>{selected.characteristics.holdingPeriod}</strong>
                </div>
                <div className="guide-char-card">
                  <span className="guide-char-label">{t('strategyGuide.applicableStocks')}</span>
                  <strong>{selected.characteristics.applicableStocks}</strong>
                </div>
                <div className="guide-char-card">
                  <span className="guide-char-label">{t('strategyGuide.riskLevel')}</span>
                  <strong>{selected.characteristics.riskLevel}</strong>
                </div>
              </div>
            </section>
          </>
        ) : (
          <div className="guide-empty">{t('strategyGuide.empty')}</div>
        )}
      </section>
    </div>
  );
}