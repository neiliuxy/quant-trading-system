import i18n from './index';

export function chartLocale(): string {
  return i18n.language === 'en' ? 'en-US' : 'zh-CN';
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(chartLocale()).format(value);
}