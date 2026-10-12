<script>
	import '../app.css';
	import { onMount } from 'svelte';
	import { initializeAuth } from '#lib/auth.js';

	let { children } = $props();

	onMount(() => {
		initializeAuth();
	});
</script>

<svelte:head>
	<title>Face Authentication & Customer Transaction System</title>
	<meta
		name="description"
		content="Secure Face Authentication and Customer Transaction System - Admin Control Portal"
	/>
</svelte:head>

{@render children()}
