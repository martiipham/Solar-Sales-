import React from 'react';
import { Line } from '@ant-design/charts';
import moment from 'moment';

const ReportsPage = () => {
  // Mock data for demonstration purposes
  const callVolumeData = [
    { date: '2023-01-01', value: 50 },
    { date: '2023-01-02', value: 60 },
    { date: '2023-01-03', value: 70 },
    // ... more data
  ];

  const conversionFunnelData = [
    { label: 'Calls', value: 80 },
    { label: 'Qualified', value: 60 },
    { label: 'Proposals', value: 40 },
    { label: 'Closed', value: 20 },
  ];

  return (
    <div>
      <h1>Reports</h1>
      
      <h2>Call Volume Over Time</h2>
      <Line
        data={callVolumeData}
        xField="date"
        yField="value"
        xAxis={{
          tickCount: 5,
          label formatter: (val) => moment(val).format('MMM D'),
        }}
        yAxis={{
          minTickInterval: 10,
          nice: true,
        }}
      />

      <h2>Lead Conversion Funnel</h2>
      {/* Create a simple bar chart here using data from conversionFunnelData */}
    </div>
  );
};

export default ReportsPage;
