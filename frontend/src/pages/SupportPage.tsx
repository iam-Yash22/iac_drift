import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import PageMeta from "@/components/common/PageMeta";

export default function SupportPage() {
  return (
    <>
      <PageMeta title="Support | IaC Driftwatch" description="Support and help information for IaC Driftwatch." />
      <PageBreadcrumb pageTitle="Support" />

      <div className="rounded-2xl border border-gray-200 bg-white p-5 lg:p-6 dark:border-gray-800 dark:bg-white/3">
        <h3 className="mb-5 text-lg font-semibold text-gray-800 lg:mb-7 dark:text-white/90">
          Support
        </h3>

        <div className="space-y-5 text-sm text-gray-700 dark:text-gray-300">
          <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
            <p className="mb-1 text-base font-semibold text-gray-900 dark:text-white">
              Contact Support.
            </p>
            <p>
              Open a ticket or send an email to our dedicated support team: <a href="mailto:exampleemail@gmail.com" className="text-brand-500 underline">exampleemail@gmail.com</a>.
            </p>
          </div>

          <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
            <p className="mb-1 text-base font-semibold text-gray-900 dark:text-white">
              Request a Feature.
            </p>
            <p>Tell us how we can improve the application to better suit your needs.</p>
          </div>

          <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
            <p className="mb-1 text-base font-semibold text-gray-900 dark:text-white">
              Report a Bug.
            </p>
            <p>Found an issue? Let our engineering team know so we can fix it.</p>
          </div>
        </div>
      </div>
    </>
  );
}
