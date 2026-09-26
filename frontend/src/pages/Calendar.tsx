import Calendar from "@/components/calendar/Calendar";
import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import PageMeta from "@/components/common/PageMeta";
import "@fullcalendar/react/skeleton.css";
import "@fullcalendar/react/themes/classic/palette.css";
import "@fullcalendar/react/themes/classic/theme.css";

export default function CalendarPage() {
  return (
    <div>
      <PageMeta
        title="Calendar | IaC DriftWatch"
        description="Calendar view for infrastructure and drift monitoring operations."
      />
      <PageBreadcrumb pageTitle="Calendar" />
      <Calendar />
    </div>
  );
}
