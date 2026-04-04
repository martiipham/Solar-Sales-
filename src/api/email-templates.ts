import { NextApiRequest, NextApiResponse } from 'next'
import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { page = 1 } = req.query
  
  try {
    const pageSize = 10
    const skip = (parseInt(page as string) - 1) * pageSize
    
    const [templates, totalCount] = await prisma.$transaction([
      prisma.emailTemplate.findMany({
        skip,
        take: pageSize,
        select: { id: true, name: true, status: true }
      }),
      prisma.emailTemplate.count()
    ])
    
    res.status(200).json({
      items: templates,
      totalPages: Math.ceil(totalCount / pageSize)
    })
  } catch (error) {
    console.error('Error fetching templates:', error)
    res.status(500).json({ error: 'Internal server error' })
  }
}
