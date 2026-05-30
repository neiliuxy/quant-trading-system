import type { StrategySpec } from './types';

type Props = {
  spec: StrategySpec;
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
};

function parseValue(type: string, raw: string): number | string | boolean {
  if (type === 'int') return parseInt(raw, 10) || 0;
  if (type === 'float') return parseFloat(raw) || 0;
  if (type === 'bool') return raw === 'true';
  return raw;
}

export default function StrategyParamsForm({ spec, value, onChange }: Props) {
  return (
    <div className="strategy-params">
      {spec.params.map((param) => {
        const current = value[param.name] ?? param.default;
        return (
          <label key={param.name}>
            {param.label}
            {param.type === 'bool' ? (
              <input
                type="checkbox"
                checked={Boolean(current)}
                onChange={(e) =>
                  onChange({ ...value, [param.name]: e.target.checked })
                }
              />
            ) : (
              <input
                type={param.type === 'int' ? 'number' : 'number'}
                step={param.type === 'float' ? 'any' : '1'}
                value={String(current)}
                onChange={(e) =>
                  onChange({ ...value, [param.name]: parseValue(param.type, e.target.value) })
                }
              />
            )}
          </label>
        );
      })}
    </div>
  );
}
