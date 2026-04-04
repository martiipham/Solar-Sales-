import { useEffect, useState } from 'react';
import { filterDataByQuery } from '../helpers';

const useFilterResults = (initialData) => {
    const [data, setData] = useState(initialData);
    const [query, setQuery] = useState('');

    useEffect(() => {
        setData(filterDataByQuery(initialData, query));
    }, [query, initialData]);

    return { data, query, setQuery };
};

export default useFilterResults;
