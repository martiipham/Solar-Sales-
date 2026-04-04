import React, { useState } from 'react';

const EmailTemplateForm = () => {
  const [formData, setFormData] = useState({
    name: '',
    subject: ''
  });

  const handleInputChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Add validation logic here before form submission
    console.log('Form Submitted:', formData);
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label>Name:</label>
        <input 
          type="text" 
          name="name" 
          value={formData.name} 
          onChange={handleInputChange}
          required />
      </div>
      <div>
        <label>Subject:</label>
        <input 
          type="text" 
          name="subject" 
          value={formData.subject} 
          onChange={handleInputChange}
          required />
      </div>
      <button type="submit">Submit</button>
    </form>
  );
};

export default EmailTemplateForm;
