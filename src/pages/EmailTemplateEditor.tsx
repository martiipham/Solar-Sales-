import React from 'react';
import { useForm } from 'react-hook-form';

const EmailTemplateEditor = () => {
  const { register, handleSubmit, formState: { errors } } = useForm();

  const onSubmit = (data) => {
    console.log(data);
  };

  return (
    <div>
      <h1>Email Template Editor</h1>
      <form onSubmit={handleSubmit(onSubmit)}>
        <div>
          <label htmlFor="templateName">Template Name:</label>
          <input id="templateName" {...register("templateName", { required: true })} />
          {errors.templateName && <span>This field is required</span>}
        </div>
        <div>
          <label htmlFor="emailSubject">Email Subject:</label>
          <input id="emailSubject" {...register("emailSubject")} />
        </div>
        <div>
          <label htmlFor="templateContent">Template Content:</label>
          <textarea id="templateContent" {...register("templateContent")}></textarea>
        </div>
        <button type="submit">Save Template</button>
      </form>
    </div>
  );
};

export default EmailTemplateEditor;
