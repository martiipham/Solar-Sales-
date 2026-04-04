import axios from 'axios';

const fetchReportsData = async (dateRange: { start: string; end: string }) => {
  const response = await axios.post('/api/reports/data', { dateRange });
  return response.data;
};

export { fetchReportsData };
