import React, { useState } from 'react';
import { Button, Form, Input } from 'antd';
import useMutation from 'useStateMachine/useMutation';

const EmailTemplatesPage = () => {
  const [form] = useForm();
  const [loading, setLoading] = useState(false);
  const mutation = useMutation('createEmailTemplate');

  const onFinish = async (values) => {
    setLoading(true);
    try {
      await mutation.mutateAsync(values);
      form.resetFields();
      message.success('Email template created successfully');
    } catch (error) {
      message.error('Error creating email template');
    }
    setLoading(false);
  };

  return (
    <Form form={form} layout="vertical" onFinish={onFinish}>
      <Form.Item
        name="subject"
        label="Subject"
        rules={[{ required: true, message: 'Please enter a subject' }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="body"
        label="Body"
        rules={[{ required: true, message: 'Please enter a body' }]}
      >
        <Input.TextArea rows={4} />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading}>
          Create
        </Button>
      </Form.Item>
    </Form>
  );
};

export default EmailTemplatesPage;
