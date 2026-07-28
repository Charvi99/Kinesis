import axios from 'axios';

// Relative base: dev uses the Vite proxy (vite.config.js /api -> :8081); prod uses
// the nginx reverse proxy in the frontend container (/api -> backend). Set
// VITE_API_URL at build time to point elsewhere (e.g. a remote API host).
const HOST = import.meta.env.VITE_API_URL || '';
const BASE = `${HOST}/api/v1`;

const api = axios.create({ baseURL: BASE, headers: { 'Content-Type': 'application/json' }, timeout: 60000 });

export const checkHealth = async () => (await axios.get(`${HOST}/health`, { timeout: 5000 })).data;

export const getConfig = async () => (await api.get('/config')).data;
export const getPortfolioState = async () => (await api.get('/portfolio/state')).data;
export const getSelection = async (limit = 50) => (await api.get('/selection', { params: { limit } })).data;
export const getTrades = async (limit = 100) => (await api.get('/trades', { params: { limit } })).data;
export const runBacktest = async (payload) => (await api.post('/backtest', payload)).data;

// Engines (named, persisted configs). The deployed one is the system's source of truth.
export const listEngines = async () => (await api.get('/engines')).data;
export const getEngine = async (id) => (await api.get(`/engines/${id}`)).data;
export const getEngineCurves = async () => (await api.get('/engines/curves')).data;
export const createEngine = async (payload) => (await api.post('/engines', payload)).data;
export const updateEngine = async (id, payload) => (await api.patch(`/engines/${id}`, payload)).data;
export const deleteEngine = async (id) => (await api.delete(`/engines/${id}`)).data;
export const deployEngine = async (id) => (await api.post(`/engines/${id}/deploy`)).data;

// Paper-trading ledger: live accounts + per-engine on/off controls.
// /enable takes a JSON body {engine_id, starting_cash?}; /disable takes engine_id as a query param.
export const listPaperAccounts = async () => (await api.get('/paper-trading/accounts')).data;
export const enablePaperTrading = async (engine_id, starting_cash) =>
  (await api.post('/paper-trading/enable', { engine_id, ...(starting_cash ? { starting_cash } : {}) })).data;
export const disablePaperTrading = async (engine_id) =>
  (await api.post('/paper-trading/disable', null, { params: { engine_id } })).data;

// Explore: sweep one knob, or compare two configs. These run real backtests, so a
// generous timeout (a sweep of N values = N full-history backtests).
const SLOW = { timeout: 120000 };
export const runSweep = async (payload) => (await api.post('/backtest/sweep', payload, SLOW)).data;
export const runCompare = async (payload) => (await api.post('/backtest/compare', payload, SLOW)).data;

export default api;
