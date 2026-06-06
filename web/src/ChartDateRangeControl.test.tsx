import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ChartDateRangeControl from './ChartDateRangeControl';

describe('ChartDateRangeControl', () => {
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

    const [startInput] = screen.getAllByPlaceholderText('YYYYMMDD');
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

    const [startInput, endInput] = screen.getAllByPlaceholderText('YYYYMMDD');
    fireEvent.change(startInput, { target: { value: '20240201' } });
    fireEvent.blur(startInput);

    expect(onChange).toHaveBeenCalledWith({ start: '20240201', end: '20241231' });

    fireEvent.change(endInput, { target: { value: '20241130' } });
    fireEvent.blur(endInput);

    expect(onChange).toHaveBeenLastCalledWith({ start: '20240201', end: '20241130' });

    fireEvent.click(screen.getByRole('button', { name: '重置' }));

    expect(onChange).toHaveBeenLastCalledWith(null);
  });
});
