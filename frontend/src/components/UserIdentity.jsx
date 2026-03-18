import { Badge } from '@/components/ui/badge'

export default function UserIdentity({ name, groups = [], className = '' }) {
  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`.trim()}>
      <span className='font-medium'>{name}</span>
      {groups.map((group) => (
        <Badge key={`${name}-${group}`} variant='secondary'>
          {group}
        </Badge>
      ))}
    </div>
  )
}
