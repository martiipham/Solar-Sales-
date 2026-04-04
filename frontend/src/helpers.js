const filterDataByQuery = (data, query) => {
    return data.filter(item => {
        // Implement actual filtering logic here
        // Example: return item.name.toLowerCase().includes(query.toLowerCase());
    });
};

export { filterDataByQuery };
