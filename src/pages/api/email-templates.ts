import { NextApiRequest, NextApiResponse } from 'next';
import supabaseClient from '../../../lib/supabase';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === 'POST') {
    try {
      const { templateName, content } = JSON.parse(req.body);

      // Insert email template into Supabase
      const response = await supabaseClient
        .from('email_templates')
        .insert([{ name: templateName, body: content }]);

      if (response.error) {
        res.status(500).json({ error: response.error.message });
      } else {
        res.status(201).json(response.data[0]);
      }
    } catch (error) {
      console.error(error);
      res.status(500).json({ error: 'Internal server error' });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
