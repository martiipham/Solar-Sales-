import React, { useState, useEffect } from 'react';

const DataTable = ({ data }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredData, setFilteredData] = useState(data);

  useEffect(() => {
    handleSearch(searchTerm);
  }, [searchTerm]);

  const handleSearch = (term) => {
    if (!term || term === '') {
      setFilteredData(data);
      return;
    }

    const filteredResults = data.filter((item) =>
      Object.values(item).some(value => 
        String(value).toLowerCase().includes(term.toLowerCase())
      )
    );

    setFilteredData(filteredResults);
  };

  return (
    <div>
      <input
        type="text"
        placeholder="Search..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
      />
      {filteredData.map((item, index) => (
        <div key={index}>
          {/* Render item fields here */}
        </div>
      ))}
    </div>
  );
};

export default DataTable;
