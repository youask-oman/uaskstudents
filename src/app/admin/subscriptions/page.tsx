import { redirect } from 'next/navigation';

export default function AdminSubscriptionsRedirect() {
    redirect('/admin/legacy/subscriptions');
}
