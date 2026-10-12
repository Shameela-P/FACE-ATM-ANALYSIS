<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	onMount(() => {
		goto('/admin/dashboard', { replaceState: true });
	});
</script>

<div style="display: none;"></div>
