/**
 * U160 - React Pump Configurator Component
 * 
 * Consumes the SAME V2 API as Excel. User selects values from dropdowns,
 * each selection triggers /evaluate which returns updated allowable options.
 * 
 * Flow:
 *   1. Load dictionary (GET /configuration-dictionary) on mount
 *   2. User selects family + series
 *   3. Each subsequent selection calls POST /evaluate
 *   4. Dropdowns re-render with only allowable values
 *   5. When complete, POST /resolve to get Part Number + SKU
 */

import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = '/api/v2';

interface FieldOptions {
  [fieldCode: string]: string[];
}

interface ResolvedCodes {
  [fieldCode: string]: string | null;
}

interface EvaluateResponse {
  family: string;
  series: string;
  valid: boolean;
  allowable_options: FieldOptions;
  resolved_codes: ResolvedCodes;
  errors: string[];
}

interface ResolveResponse {
  family: string;
  part_number: string;
  sku: string;
  configuration_signature: string;
  existing_configuration: boolean;
}

export const PumpConfigurator: React.FC = () => {
  const [family, setFamily] = useState<string>('FYBROC');
  const [series, setSeries] = useState<string>('');
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [allowableOptions, setAllowableOptions] = useState<FieldOptions>({});
  const [resolvedCodes, setResolvedCodes] = useState<ResolvedCodes>({});
  const [resolveResult, setResolveResult] = useState<ResolveResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Evaluate configuration whenever selections change
  const evaluate = useCallback(async (currentSeries: string, currentSelections: Record<string, string>) => {
    if (!currentSeries) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/families/${family}/configurations/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          series: currentSeries,
          selections: currentSelections,
        }),
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);

      const data: EvaluateResponse = await response.json();
      setAllowableOptions(data.allowable_options);
      setResolvedCodes(data.resolved_codes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [family]);

  // Handle selection change
  const handleSelection = (fieldCode: string, value: string) => {
    const updated = { ...selections, [fieldCode]: value };
    setSelections(updated);
    setResolveResult(null);
    evaluate(series, updated);
  };

  // Handle series change (resets everything)
  const handleSeriesChange = (newSeries: string) => {
    setSeries(newSeries);
    setSelections({});
    setResolveResult(null);
    evaluate(newSeries, {});
  };

  // Resolve final configuration
  const handleResolve = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/families/${family}/configured-products/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          series,
          selections,
          segment_codes: resolvedCodes,
        }),
      });

      if (!response.ok) throw new Error(`Resolve error: ${response.status}`);

      const data: ResolveResponse = await response.json();
      setResolveResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="pump-configurator">
      <h1>Pump Configurator</h1>

      {/* Family selector */}
      <div className="field-group">
        <label>Family</label>
        <select value={family} onChange={(e) => setFamily(e.target.value)}>
          <option value="FYBROC">Fybroc</option>
          <option value="DEAN">Dean</option>
        </select>
      </div>

      {/* Series selector */}
      <div className="field-group">
        <label>Series</label>
        <select value={series} onChange={(e) => handleSeriesChange(e.target.value)}>
          <option value="">-- Select Series --</option>
          <option value="1500">1500</option>
          <option value="1530">1530</option>
          <option value="1600">1600</option>
          <option value="1630">1630</option>
          <option value="2530">2530</option>
          <option value="3000">3000</option>
          <option value="5500">5500</option>
        </select>
      </div>

      {/* Dynamic field dropdowns — only shows allowable options */}
      {Object.entries(allowableOptions).map(([fieldCode, options]) => (
        <div className="field-group" key={fieldCode}>
          <label>{fieldCode.replace(/_/g, ' ')}</label>
          <select
            value={selections[fieldCode] || ''}
            onChange={(e) => handleSelection(fieldCode, e.target.value)}
          >
            <option value="">-- Select --</option>
            {options.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </div>
      ))}

      {/* Already selected fields */}
      {Object.keys(selections).length > 0 && (
        <div className="selections-summary">
          <h3>Current Selections</h3>
          {Object.entries(selections).map(([field, value]) => (
            <div key={field}>
              <strong>{field}:</strong> {value}
              {resolvedCodes[field] && <span className="code"> → code: {resolvedCodes[field]}</span>}
            </div>
          ))}
        </div>
      )}

      {/* Resolve button */}
      {Object.keys(selections).length > 0 && (
        <button onClick={handleResolve} disabled={loading}>
          {loading ? 'Resolving...' : 'Generate Part Number & SKU'}
        </button>
      )}

      {/* Result */}
      {resolveResult && (
        <div className="result">
          <h3>Configured Product</h3>
          <div><strong>Part Number:</strong> {resolveResult.part_number}</div>
          <div><strong>SKU:</strong> {resolveResult.sku}</div>
          <div><strong>Signature:</strong> {resolveResult.configuration_signature.substring(0, 16)}...</div>
          <div><strong>Reused:</strong> {resolveResult.existing_configuration ? 'Yes' : 'No (new)'}</div>
        </div>
      )}

      {/* Error display */}
      {error && <div className="error">{error}</div>}
      {loading && <div className="loading">Loading...</div>}
    </div>
  );
};

export default PumpConfigurator;
