import React, { useEffect, useState } from 'react';
import { Table, Pagination, Button } from '@nextui-org/react';
import axios from 'axios';

const EmailTemplates = () => {
    const [templates, setTemplates] = useState([]);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);

    useEffect(() => {
        fetchTemplates(page);
    }, [page]);

    const fetchTemplates = async (pageNumber: number) => {
        try {
            const response = await axios.get(`/api/email-templates?page=${pageNumber}&limit=10`);
            setTemplates(response.data.templates);
            setTotalPages(Math.ceil(response.data.total / 10));
        } catch (error) {
            console.error("Failed to fetch email templates:", error);
        }
    };

    const handleRefresh = async () => {
        try {
            await fetchTemplates(page);
        } catch (error) {
            console.error("Failed to refresh templates:", error);
        }
    };

    return (
        <div>
            <Button onClick={handleRefresh} auto color="primary" ghost style={{ marginBottom: '10px' }}>Refresh</Button>
            <Table aria-label="Email Templates Table">
                <Table.Header>
                    <Table.Column>Template Name</Table.Column>
                    <Table.Column>Status</Table.Column>
                </Table.Header>
                <Table.Body>
                    {templates.map((template: any) => (
                        <Table.Row key={template.id}>
                            <Table.Cell>{template.name}</Table.Cell>
                            <Table.Cell>{template.status}</Table.Cell>
                        </Table.Row>
                    ))}
                </Table.Body>
            </Table>
            <Pagination
                total={totalPages}
                page={page}
                onChange={(newPage) => setPage(newPage)}
                showControls
            />
        </div>
    );
};

export default EmailTemplates;
