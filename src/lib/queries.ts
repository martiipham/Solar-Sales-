export const listEmailTemplates = async (page: number = 1) => {
  return fetchAPI('/api/email-templates', {
    method: 'GET',
    params: { page }
  })
}
