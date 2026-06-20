import { useEffect, useRef, useState } from 'react';
import { Check, Languages } from 'lucide-react';
import i18n from '../i18n';

type SupportedLng = 'zh' | 'en';

const LABELS: Record<SupportedLng, string> = { zh: '中文', en: 'English' };
const ABBR: Record<SupportedLng, string> = { zh: 'ZH', en: 'EN' };

function setLang(lng: SupportedLng) {
  void i18n.changeLanguage(lng);
  localStorage.setItem('lang', lng);
}

export function LanguageSwitcher() {
  const [open, setOpen] = useState(false);
  const [lng, setLng] = useState<SupportedLng>(() =>
    i18n.language === 'en' ? 'en' : 'zh'
  );
  const ref = useRef<HTMLDivElement>(null);

  // React to external language changes (e.g., from tests or future programmatic APIs).
  useEffect(() => {
    const handler = (next: string) => setLng(next === 'en' ? 'en' : 'zh');
    i18n.on('languageChanged', handler);
    return () => i18n.off('languageChanged', handler);
  }, []);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  function pick(next: SupportedLng) {
    setLang(next);
    setLng(next);
    setOpen(false);
  }

  return (
    <div className="lang-switcher" ref={ref}>
      <button
        type="button"
        className="lang-switcher-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Languages size={16} />
        <span>{ABBR[lng]}</span>
      </button>
      {open && (
        <div className="lang-switcher-menu" role="menu">
          {(Object.keys(LABELS) as SupportedLng[]).map((code) => (
            <button
              key={code}
              type="button"
              role="menuitemradio"
              aria-checked={lng === code}
              className={`lang-switcher-item ${lng === code ? 'active' : ''}`}
              onClick={() => pick(code)}
            >
              <span>{LABELS[code]}</span>
              {lng === code && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default LanguageSwitcher;
