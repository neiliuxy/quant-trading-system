import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import zhDict from './locales/zh.json';
import enDict from './locales/en.json';

export const STORAGE_KEY = 'lang';
export type SupportedLng = 'zh' | 'en';

function readSavedLng(): SupportedLng {
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved === 'en' ? 'en' : 'zh';
}

i18n
  .use(initReactI18next)
  .init({
    resources: {
      zh: { common: zhDict as Record<string, string> },
      en: { common: enDict as Record<string, string> },
    },
    lng: readSavedLng(),
    fallbackLng: 'zh',
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    saveMissing: import.meta.env.DEV,
    missingKeyHandler: (_lngs, _ns, key) => {
      if (import.meta.env.DEV) {
        console.warn(`[i18n] missing key: ${key}`);
      }
    },
  });

export default i18n;
