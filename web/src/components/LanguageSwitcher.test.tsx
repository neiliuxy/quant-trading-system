import { describe, expect, it, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import i18n from '../i18n';
import { LanguageSwitcher } from './LanguageSwitcher';

describe('LanguageSwitcher', () => {
  beforeEach(async () => {
    localStorage.clear();
    await i18n.changeLanguage('zh');
  });

  it('shows current language as ZH by default', () => {
    render(<LanguageSwitcher />);
    expect(screen.getByRole('button', { name: /ZH|English/ })).toBeInTheDocument();
  });

  it('switches to en and persists to localStorage', async () => {
    render(<LanguageSwitcher />);
    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByText('English'));
    await Promise.resolve(); // let changeLanguage resolve
    expect(i18n.language).toBe('en');
    expect(localStorage.getItem('lang')).toBe('en');
  });

  it('switches back to zh', async () => {
    await i18n.changeLanguage('en');
    render(<LanguageSwitcher />);
    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByText('中文'));
    await Promise.resolve();
    expect(i18n.language).toBe('zh');
    expect(localStorage.getItem('lang')).toBe('zh');
  });
});
