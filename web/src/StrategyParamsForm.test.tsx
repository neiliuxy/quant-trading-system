import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import StrategyParamsForm from './StrategyParamsForm';
import type { StrategySpec } from './types';

const spec: StrategySpec = {
  id: 'demo',
  name: 'Demo',
  description: 'demo',
  params: [
    { name: 'fast_ma', label: 'Fast MA', type: 'int', default: 10 },
    { name: 'enabled', label: 'Enabled', type: 'bool', default: true },
  ],
};

describe('StrategyParamsForm', () => {
  it('keeps typed number input local until blur', () => {
    const onChange = vi.fn();

    render(<StrategyParamsForm spec={spec} value={{ fast_ma: 10, enabled: true }} onChange={onChange} />);

    const input = screen.getByLabelText('Fast MA') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '25' } });

    expect(input.value).toBe('25');
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.blur(input);

    expect(onChange).toHaveBeenCalledWith({ fast_ma: 25, enabled: true });
  });

  it('updates checkbox immediately', () => {
    const onChange = vi.fn();

    render(<StrategyParamsForm spec={spec} value={{ fast_ma: 10, enabled: true }} onChange={onChange} />);

    fireEvent.click(screen.getByLabelText('Enabled'));

    expect(onChange).toHaveBeenCalledWith({ fast_ma: 10, enabled: false });
  });
});
