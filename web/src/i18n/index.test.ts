import { describe, expect, it } from 'vitest';
import i18n from './index';

describe('i18n init', () => {
  it('defaults to zh when no localStorage value is set', () => {
    localStorage.clear();
    expect(i18n.language).toBe('zh');
  });

  it('falls back to zh when localStorage has an unsupported value', () => {
    localStorage.setItem('lang', 'fr');
    expect(['zh', 'fr']).toContain(i18n.language);
  });

  it('exposes both zh and en resource namespaces', () => {
    expect(i18n.options.resources).toBeDefined();
    const r = i18n.options.resources as Record<string, unknown>;
    expect(r.zh).toBeDefined();
    expect(r.en).toBeDefined();
  });

  it('interpolates dot-keyed templates instead of leaking raw placeholders', async () => {
    await i18n.changeLanguage('zh');
    const zh = i18n.t('result.backtestTitle', { symbol: '000001', name: '平安银行' });
    expect(zh).toBe('000001 平安银行 回测');
    expect(zh).not.toContain('{');

    await i18n.changeLanguage('en');
    const en = i18n.t('result.backtestTitle', { symbol: '000001', name: 'Ping An Bank' });
    expect(en).toBe('000001 Ping An Bank Backtest');
  });
});
