import classroomCover from './projects/classroom-cover.png'
import featuredCover from './projects/featured-cover.png'
import lostFoundCover from './projects/lost-found-cover.png'

export const projectCovers = [featuredCover, lostFoundCover, classroomCover] as const

export function getProjectCover(projectId: number, index = 0): string {
  return projectCovers[Math.abs(projectId + index) % projectCovers.length] ?? featuredCover
}
