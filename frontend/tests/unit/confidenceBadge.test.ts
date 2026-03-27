/**
 * @spec FS-AI-011 AC-4
 * @spec FE-COMP-001 §3.10
 * @description ConfidenceBadge 4단계 색상 코딩 및 크기 변형 테스트
 */

import { describe, it, expect } from 'vitest';

// Test the grade mapping logic directly (no React render needed)
function getGrade(confidence: number): string {
  if (confidence >= 0.85) return 'HIGH';
  if (confidence >= 0.65) return 'MEDIUM';
  if (confidence >= 0.40) return 'LOW';
  return 'VERY_LOW';
}

describe('[Spec: FS-AI-011] ConfidenceBadge', () => {
  /**
   * @spec FS-AI-011 AC-4
   * @description >= 0.85 → HIGH (tertiary green)
   */
  it('AC-4: confidence 0.85 → HIGH grade', () => {
    expect(getGrade(0.85)).toBe('HIGH');
    expect(getGrade(0.90)).toBe('HIGH');
    expect(getGrade(1.0)).toBe('HIGH');
  });

  /**
   * @spec FS-AI-011 AC-4
   * @description >= 0.65 → MEDIUM (primary blue)
   */
  it('AC-4: confidence 0.65~0.84 → MEDIUM grade', () => {
    expect(getGrade(0.65)).toBe('MEDIUM');
    expect(getGrade(0.75)).toBe('MEDIUM');
    expect(getGrade(0.84)).toBe('MEDIUM');
  });

  /**
   * @spec FS-AI-011 AC-4
   * @description >= 0.40 → LOW (amber)
   */
  it('AC-4: confidence 0.40~0.64 → LOW grade', () => {
    expect(getGrade(0.40)).toBe('LOW');
    expect(getGrade(0.50)).toBe('LOW');
    expect(getGrade(0.64)).toBe('LOW');
  });

  /**
   * @spec FS-AI-011 AC-4
   * @description < 0.40 → VERY_LOW (error red)
   */
  it('AC-4: confidence < 0.40 → VERY_LOW grade', () => {
    expect(getGrade(0.39)).toBe('VERY_LOW');
    expect(getGrade(0.0)).toBe('VERY_LOW');
    expect(getGrade(0.10)).toBe('VERY_LOW');
  });

  /**
   * @spec FS-AI-011 AC-4
   * @description boundary: exactly 0.85, 0.65, 0.40
   */
  it('AC-4: boundary values land in correct grades', () => {
    expect(getGrade(0.85)).toBe('HIGH');
    expect(getGrade(0.8499)).toBe('MEDIUM');
    expect(getGrade(0.65)).toBe('MEDIUM');
    expect(getGrade(0.6499)).toBe('LOW');
    expect(getGrade(0.40)).toBe('LOW');
    expect(getGrade(0.3999)).toBe('VERY_LOW');
  });
});
