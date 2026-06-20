import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ChartDateRangeControl from './ChartDateRangeControl';
import i18n from './i18n';

describe('ChartDateRangeControl', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('zh');
  });

  afterEach(async () => {
    await i18n.changeLanguage('zh');
    localStorage.clear();
  });

  it('does not apply partial input', () => {
    const onChange = vi.fn();

    render(
      <ChartDateRangeControl
        value={null}
        defaultStart="20240101"
        defaultEnd="20241231"
        onChange={onChange}
      />
    );

    const [startInput] = screen.getAllByPlaceholderText(i18n.t('dateRange.placeholder'));
    fireEvent.change(startInput, { target: { value: '2024' } });
    fireEvent.blur(startInput);

    expect(onChange).not.toHaveBeenCalled();
  });

  it('applies full dates on blur and can reset', () => {
    const onChange = vi.fn();

    render(
      <ChartDateRangeControl
        value={null}
        defaultStart="20240101"
        defaultEnd="20241231"
        onChange={onChange}
      />
    );

    const [startInput, endInput] = screen.getAllByPlaceholderText(i18n.t('dateRange.placeholder'));
    fireEvent.change(startInput, { target: { value: '20240201' } });
    fireEvent.blur(startInput);

    expect(onChange).toHaveBeenCalledWith({ start: '20240201', end: '20241231' });

    fireEvent.change(endInput, { target: { value: '20241130' } });
    fireEvent.blur(endInput);

    expect(onChange).toHaveBeenLastCalledWith({ start: '20240201', end: '20241130' });

    fireEvent.click(screen.getByRole('button', { name: i18n.t('dateRange.reset') }));

    expect(onChange).toHaveBeenLastCalledWith(null);
  });
});

describe('ChartDateRangeControl locale switching', () => {
  afterEach(async () => {
    await i18n.changeLanguage('zh');
    localStorage.clear();
  });

  it('renders Chinese labels when locale is zh', async () => {
    await i18n.changeLanguage('zh');
    render(
      <ChartDateRangeControl
        value={null}
        defaultStart="20240101"
        defaultEnd="20241231"
        onChange={() => {}}
      />
    );
    expect(screen.getByRole('button', { name: i18n.t('dateRange.reset') })).toBeInTheDocument();
  });

  it('renders English labels when locale is en', async () => {
    await i18n.changeLanguage('en');
    render(
      <ChartDateRangeControl
        value={null}
        defaultStart="20240101"
        defaultEnd="20241231"
        onChange={() => {}}
      />
    );
    expect(screen.getByRole('button', { name: i18n.t('dateRange.reset') })).toBeInTheDocument();
  });
});
