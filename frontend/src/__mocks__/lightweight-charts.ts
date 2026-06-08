export const createChart = jest.fn(() => ({
  addAreaSeries: jest.fn(() => ({
    setData: jest.fn(),
    update: jest.fn(),
  })),
  addLineSeries: jest.fn(() => ({
    setData: jest.fn(),
    update: jest.fn(),
  })),
  addCandlestickSeries: jest.fn(() => ({
    setData: jest.fn(),
    update: jest.fn(),
  })),
  timeScale: jest.fn(() => ({
    fitContent: jest.fn(),
    scrollToRealTime: jest.fn(),
  })),
  applyOptions: jest.fn(),
  resize: jest.fn(),
  remove: jest.fn(),
  subscribeCrosshairMove: jest.fn(),
  unsubscribeCrosshairMove: jest.fn(),
}));

export const ColorType = { Solid: 'solid' };
export const CrosshairMode = { Normal: 0 };
export const LineStyle = { Solid: 0 };
