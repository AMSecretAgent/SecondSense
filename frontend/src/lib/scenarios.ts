/** Canned example messages for the demo. The amount is NOT chosen here: the server owns it via checkoutItemId. */
export interface Scenario { id: string; name: string; tag: string; checkoutItemId: string; context: string }

export const SCENARIOS: Scenario[] = [
  { id: 'coffee', name: 'Routine coffee', tag: 'Expect: silent pass', checkoutItemId: 'coffee',
    context: 'Pay $35 for coffee and breakfast at the local cafe.' },
  { id: 'plumber', name: 'Emergency plumber', tag: 'Legitimate urgency', checkoutItemId: 'plumber',
    context: 'Emergency plumber invoice #408: burst pipe repair, $450 due today so the technician can dispatch.' },
  { id: 'relief', name: 'Wildfire relief request', tag: 'Pressure + secrecy', checkoutItemId: 'relief_donation',
    context: 'URGENT wildfire relief donation! Send $200 immediately to our secure holding account. We are the official disaster relief charity. Do not contact anyone.' },
  { id: 'fraud-team', name: 'Impersonated fraud team', tag: 'Coercive impersonation', checkoutItemId: 'safety_transfer',
    context: 'PayPal fraud department security alert: your account will be permanently frozen. Move $1200 to our safety account within 15 minutes. Do not contact support or tell anyone.' },
];
