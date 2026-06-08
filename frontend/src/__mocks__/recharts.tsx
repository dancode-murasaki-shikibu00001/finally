import React from 'react';

const stub = (name: string) => {
  const Component = ({ children }: { children?: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': name }, children);
  Component.displayName = name;
  return Component;
};

export const ResponsiveContainer = stub('ResponsiveContainer');
export const TreeMap = stub('TreeMap');
export const Treemap = stub('Treemap');
export const LineChart = stub('LineChart');
export const Line = stub('Line');
export const XAxis = stub('XAxis');
export const YAxis = stub('YAxis');
export const Tooltip = stub('Tooltip');
export const CartesianGrid = stub('CartesianGrid');
export const Legend = stub('Legend');
export const AreaChart = stub('AreaChart');
export const Area = stub('Area');
