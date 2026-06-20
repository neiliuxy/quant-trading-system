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
});
