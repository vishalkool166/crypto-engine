import { motion } from 'framer-motion'
import { Server, Cpu, HardDrive, MemoryStick, Wifi, WifiOff } from 'lucide-react'
import { cn } from '@/lib/utils'
import CollapsibleSection from '@/components/ui/CollapsibleSection'

interface Container {
  name:    string
  status:  string
  mem_mb:  number
  mem_pct: number
  cpu_pct: number
}

interface SystemData {
  cpuPct:      number
  ramPct:      number
  ramUsedMb:   number
  ramTotalMb:  number
  diskPct:     number
  diskUsedGb:  number
  diskTotalGb: number
  uptimeStr:   string
  containers:  Container[]
}

interface WsStreams {
  markPrice: boolean
  userData:  boolean
  kline:     boolean
  ticker:    boolean
  cached:    number
}

interface Props {
  system:     SystemData | null
  wsStreams:  WsStreams
  wsConnected:boolean
  redisConnected: boolean
  engineOk:   boolean
  mlEnabled:  boolean
  mlProgress: { closed: number; required: number; pct: number; message: string }
}

function ResourceCard({
  icon: Icon, label, value, unit, warn, critical, detail,
}: {
  icon:      React.ElementType
  label:     string
  value:     number
  unit:      string
  warn?:     boolean
  critical?: boolean
  detail?:   string
}) {
  const color    = critical ? 'text-[hsl(var(--chart-2))]' : warn ? 'text-[hsl(var(--chart-4))]' : 'text-foreground'
  const barColor = critical ? 'bg-[hsl(var(--chart-2))]' : warn ? 'bg-[hsl(var(--chart-4))]' : 'bg-[hsl(var(--chart-1))]'

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <p className="label-xs">{label}</p>
      </div>
      <p className={cn('value-md', color)}>{value}{unit}</p>
      {detail && <p className="text-xs font-mono text-muted-foreground mt-0.5">{detail}</p>}
      <div className="mt-3 h-1 w-full rounded-full bg-muted overflow-hidden">
        <motion.div
          initial    = {{ width: 0 }}
          animate    = {{ width: `${value}%` }}
          transition = {{ duration: 0.6, ease: 'easeOut' }}
          className  = {cn('h-full rounded-full', barColor)}
        />
      </div>
    </div>
  )
}

function ServiceRow({
  label, description, ok, neutral, neutralLabel,
}: {
  label:         string
  description:   string
  ok:            boolean | undefined
  neutral?:      boolean
  neutralLabel?: string
}) {
  return (
    <div className="flex items-center justify-between px-6 py-4">
      <div>
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
      </div>
      <div className="flex items-center gap-2">
        <span className={cn(
          'h-1.5 w-1.5 rounded-full',
          neutral ? 'bg-[hsl(var(--chart-4))]' : ok ? 'bg-[hsl(var(--chart-1))]' : 'bg-[hsl(var(--chart-2))]'
        )} />
        <span className={cn(
          'text-xs font-medium',
          neutral ? 'text-[hsl(var(--chart-4))]' : ok ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
        )}>
          {neutral ? neutralLabel : ok ? 'Operational' : 'Down'}
        </span>
      </div>
    </div>
  )
}

function WsRow({ label, description, ok }: { label: string; description: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between px-6 py-3.5">
      <div className="flex items-center gap-3">
        {ok
          ? <Wifi    className="h-3.5 w-3.5 text-[hsl(var(--chart-1))]" />
          : <WifiOff className="h-3.5 w-3.5 text-[hsl(var(--chart-2))]" />
        }
        <div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      <span className={cn('text-xs font-medium', ok ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]')}>
        {ok ? 'Connected' : 'Down'}
      </span>
    </div>
  )
}

export default function SystemInfra({ system, wsStreams, wsConnected, redisConnected, engineOk, mlEnabled, mlProgress }: Props) {
  return (
    <div className="space-y-4">
      {system && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <ResourceCard icon={Cpu}         label="CPU"  value={system.cpuPct}  unit="%" warn={system.cpuPct > 80}  critical={system.cpuPct > 95} />
          <ResourceCard icon={MemoryStick} label="RAM"  value={system.ramPct}  unit="%" warn={system.ramPct > 85}  critical={system.ramPct > 95}  detail={`${system.ramUsedMb}MB / ${system.ramTotalMb}MB`} />
          <ResourceCard icon={HardDrive}   label="Disk" value={system.diskPct} unit="%" warn={system.diskPct > 80} critical={system.diskPct > 90} detail={`${system.diskUsedGb}GB / ${system.diskTotalGb}GB`} />
          <div className="rounded-lg border border-border bg-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <Server className="h-4 w-4 text-muted-foreground" />
              <p className="label-xs">Uptime</p>
            </div>
            <p className="value-md text-foreground">{system.uptimeStr}</p>
          </div>
        </div>
      )}

      <CollapsibleSection title="Services" defaultOpen>
        <div className="divide-y divide-border">
          <ServiceRow label="Signal Engine" description="FastAPI backend"   ok={engineOk}       />
          <ServiceRow label="Redis"         description="Cache and pub/sub" ok={redisConnected}  />
          <ServiceRow
            label        = "ML Model"
            description  = {mlProgress.message}
            ok           = {mlEnabled}
            neutral      = {!mlEnabled}
            neutralLabel = {`${mlProgress.pct}% ready`}
          />
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="WebSocket Streams" defaultOpen>
        <div className="divide-y divide-border">
          <WsRow label="Mark Price"  description={`Real-time prices · ${wsStreams.cached} cached`} ok={wsStreams.markPrice} />
          <WsRow label="Ticker"      description="24h change · funding rates"                      ok={wsStreams.ticker}    />
          <WsRow label="Kline 15M"   description="Candle close events · trigger"                   ok={wsStreams.kline}     />
          <WsRow label="User Data"   description="Order fills · position updates"                  ok={wsStreams.userData}  />
        </div>
      </CollapsibleSection>

      {system?.containers && system.containers.length > 0 && (
        <CollapsibleSection title="Containers" count={system.containers.length}>
          <div className="divide-y divide-border">
            {system.containers.map((c, i) => (
              <motion.div
                key        = {c.name}
                initial    = {{ opacity: 0 }}
                animate    = {{ opacity: 1 }}
                transition = {{ delay: i * 0.04 }}
                className  = "flex items-center justify-between px-6 py-3.5"
              >
                <div className="flex items-center gap-3">
                  <span className={cn(
                    'h-1.5 w-1.5 rounded-full',
                    c.status === 'running' ? 'bg-[hsl(var(--chart-1))]' : 'bg-[hsl(var(--chart-2))]'
                  )} />
                  <span className="text-sm font-mono font-medium text-foreground">{c.name}</span>
                  <span className="text-xs text-muted-foreground capitalize">{c.status}</span>
                </div>
                <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground">
                  <span>CPU {c.cpu_pct}%</span>
                  <span>RAM {c.mem_mb}MB</span>
                </div>
              </motion.div>
            ))}
          </div>
        </CollapsibleSection>
      )}
    </div>
  )
}