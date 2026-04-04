import { useState } from 'react';
import SupabaseClient from '../../../lib/supabase';

export default function Page() {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    amount: null,
  });

  const handleFormChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const { user } = SupabaseClient.auth.api.getUserByCookie(document.cookie);

    if (!user) {
      alert('Please log in to create a proposal.');
      return;
    }

    try {
      const { error } = await SupabaseClient.from('proposals').insert({
        title: formData.title,
        description: formData.description,
        amount: Number(formData.amount),
        user_id: user.id,
      });

      if (error) throw error;

      alert('Proposal saved successfully!');
      window.location.href = '/proposals';
    } catch (error) {
      console.error('Error saving proposal:', error);
      alert('Failed to save proposal. Please try again.');
    }
  };

  return (
    <div>
      <h1>Create Proposal</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="title">Title:</label>
        <input
          type="text"
          id="title"
          name="title"
          value={formData.title}
          onChange={handleFormChange}
          required
        />
        <br />
        <label htmlFor="description">Description:</label>
        <textarea
          id="description"
          name="description"
          value={formData.description}
          onChange={handleFormChange}
          rows="4"
          required
        />
        <br />
        <label htmlFor="amount">Amount (USD):</label>
        <input
          type="number"
          id="amount"
          name="amount"
          value={formData.amount}
          onChange={handleFormChange}
          step="0.01"
          min="0.01"
          required
        />
        <br />
        <button type="submit">Submit Proposal</button>
      </form>
    </div>
  );
}
