import dynamic from "next/dynamic";

const MapView = dynamic(() => import("./MapViewClient"), {
  loading: () => (
    <div className="grid h-[420px] place-items-center rounded-[28px] border border-white/70 bg-white/80 text-sm text-slate-500">
      Loading map…
    </div>
  ),
  ssr: false,
});

export { MapView };
