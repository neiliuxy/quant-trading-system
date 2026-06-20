import { describe, expect, it } from 'vitest';
import i18n from './index';
import { chartLocale, formatNumber } from './locale';

describe('locale helpers', () => {
  it('chartLocale returns zh-CN when language is zh', async () => {
    await i18n.changeLanguage('zh');
    expect(chartLocale()).toBe('zh-CN');
  });

  it('chartLocale returns en-US when language is en', async () => {
    await i18n.changeLanguage('en');
    expect(chartLocale()).toBe('en-US');
  });

  it('formatNumber returns a string for integers', () => {
    expect(typeof formatNumber(1234)).toBe('string');
    expect(formatNumber(1234)).toMatch(/1[,]?234/);
  });

  it('formatNumber handles zero', () => {
    expect(formatNumber(0)).toBe('0');
  });
});