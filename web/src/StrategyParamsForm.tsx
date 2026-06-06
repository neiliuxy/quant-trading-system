import { memo, useEffect, useState } from 'react';
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

function buildDraft(spec: StrategySpec, value: Record<string, unknown>): Record<string, string | boolean> {
  return Object.fromEntries(
    spec.params.map((param) => {
      const current = value[param.name] ?? param.default;
      return [param.name, param.type === 'bool' ? Boolean(current) : String(current)];
    })
  );
}

function StrategyParamsForm({ spec, value, onChange }: Props) {
  const [draft, setDraft] = useState<Record<string, string | boolean>>(() => buildDraft(spec, value));

  useEffect(() => {
    setDraft(buildDraft(spec, value));
  }, [spec, value]);

  function commitParam(name: string, type: string, raw: string) {
    onChange({ ...value, [name]: parseValue(type, raw) });
  }

  return (
    <div className="strategy-params">
      {spec.params.map((param) => {
        const current = value[param.name] ?? param.default;
        const draftValue = draft[param.name];
        return (
          <label key={param.name}>
            {param.label}
            {param.type === 'bool' ? (
              <input
                type="checkbox"
                checked={Boolean(current)}
                onChange={(e) => {
                  setDraft((prev) => ({ ...prev, [param.name]: e.target.checked }));
                  onChange({ ...value, [param.name]: e.target.checked });
                }}
              />
            ) : (
              <input
                type={param.type === 'int' ? 'number' : 'number'}
                step={param.type === 'float' ? 'any' : '1'}
                value={typeof draftValue === 'string' ? draftValue : String(current)}
                onChange={(e) =>
                  setDraft((prev) => ({ ...prev, [param.name]: e.target.value }))
                }
                onBlur={(e) => commitParam(param.name, param.type, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.currentTarget.blur();
                  }
                }}
              />
            )}
          </label>
        );
      })}
    </div>
  );
}

export default memo(StrategyParamsForm);
