import dynamic from "next/dynamic";

const PropertyMapClient = dynamic(() => import("./PropertyMapClient"), {
  ssr: false,
  loading: () => (
    <div className="grid h-screen place-items-center rounded-[32px] border border-white/70 bg-white/80 text-sm text-slate-500 md:h-[640px]">
      Loading map…
    </div>
  ),
});

export function PropertyMap({ country }: { country: string }) {
  return <PropertyMapClient country={country} />;
}
