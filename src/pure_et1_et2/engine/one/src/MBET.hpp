#include <limits>
#include <chrono>
#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <functional>
#include <numeric>
#include <set>
#include <stdexcept>
#include <string>
#include <list>
#include <deque>
#include <map>
#include <type_traits>
#include <memory>
#include <memory_resource>
#include <unordered_map>
#include <utility>
#include <vector>
#include <cassert>

#include "common/bigraph.hpp"
#include "common/timer.hpp"

// #define MBETM
// #define ONLY_COUNTING
// #define OUTPUT_RESULT

static constexpr size_t NumBits = std::numeric_limits<size_t>::digits;
static constexpr size_t HighestBit = 1UL << (NumBits - 1);
using CompressedNeighbors = std::vector<std::pair<size_t, size_t>>;

struct MBETFastConfig {
  bool st = true;
  bool et = false;
  bool tg = false;
  size_t kappa = 1;
  size_t et2_max_defects = 28; // max missing edges for exact bounded MIS enumeration
  size_t et2_max_mis = 512;     // avoid materializing large batches before fallback
  bool et2_reuse_buffers = false; // V54 reuse verifier and MIS scratch across independent Find calls
  bool et2_root_degree_gate = false; // V54 exact necessary condition, no false pruning
  bool et2_trie_prefix_reuse = false; // V54 sort and reuse output trie prefixes
  size_t et2_reuse_min_mis = 3; // only sort/reuse on sufficiently large batches
  size_t v56_terminal = 0; // 0=off, 1=A fixed, 2=A guided, 3=B mask, 4=C component
  size_t v56_min_paths = 5;
  size_t v56_max_paths = 32;
  size_t v56_max_cols = 128;
  size_t v56_max_bits = 12;
  size_t v56_component_cap = 10;
  bool v56_prefork = false; // D: provably empty-predecessor Fork skip
  // V57: B-only, preserve exact AND closure and global result ownership.
  bool v57_mask_direct = false; // emit paths from compact masks, no output vector
  bool v57_mask_prefix = false; // lexicographic mask order + Result Tree prefix reuse
  bool v57_mask_fast_closure = false; // reuse stamp array and closed-mask buffer
  size_t v57_mask_output_factor = 0; // 0=off; if closure has > n*factor masks, fall back
  size_t v58_min_path_work = 0; // cheap proxy end_count*max_end_len, 0 disables
  size_t v58_max_length_spread = 0; // 0 disables cheap length-heterogeneity gate
  // V59: mutually exclusive terminal selection. No solver mutates Result Tree before success.
  // 0=V58 legacy cascading; 1=mask-or-DFS; 2=ET1-or-DFS;
  // 3=ET2-or-DFS; 4=cost dispatcher; 5=strict dispatcher; 6=mask+ET1 dispatcher.
  size_t v59_dispatch = 0;
  bool v59_no_et2_fallback = false; // legacy V58 ablation: skip ET2 if bitmask misses
  size_t v59_work_gate = 96;        // cheap n * (maximum candidate length)
  size_t v59_mask_min_paths = 8;
  size_t v59_et2_max_paths = 12;   // cap on plausible ET2 candidates
  // V60: exact small-defect preprocessing before any per-terminal row materialization.
  bool v62_tree_mask = false; // V62: propagate changing-column mask along candidate trie (no per-leaf rescan)
  bool v62_mask_cursor = false; // V62: reuse monotonically advancing changing-column index on trie edges
  bool v61_fast_sort = false; // reverse closure masks once before integer sort
  bool v61_fast_emit = false; // precompute changing-column lookup for mask output
  bool v61_flat_rows = false; // retain packed successful rows from the first candidate traversal
  bool v60_lazy_mask = false; // stream intersection/union, stop when variation exceeds cap
  bool v60_root_gate = false; // O(1) necessary spread/root-first-column bound
  size_t v60_mask_risk_factor = 0; // heuristic 2^variation <= factor*input_paths, 0=off

  size_t et_min_paths = 3;
  bool et_cardinality_gate = false; // Distinct terminal rows <= max candidate path length + 1
  bool et_root_enabled = true; // For independent ET/TG cost attribution.
  bool et_root_shape_gate = false; // Provably necessary matching-terminal root structure.
  bool et_root_summary = false; // V50: O(1) ET admissibility via maintained dummy-root metadata.
  bool et_root_summary_verify = false; // Debug-only: rescan and assert root aggregate correctness.
  bool et_reuse_scratch = false; // Reuse ET's short-lived verifier buffers.
  size_t tg_min_family = 0; // Optional cheap global admission gate; 0=off.
  bool tg2_prefix = false; // V55 experimental 2-biplex-aware canonical prefix TG
  bool tg2_require_nonmatching = false; // accept only prefix containing a degree-2 defect endpoint
  bool tg_preorder_fuse = false; // V49: discover canonical TG prefix during mandatory dfs_pre.
  size_t tg_phase_sample_period = 0; // 0=off, 4096=sample every 4096 Find calls.
  bool et_tg_shared = false; // V48: ET stream exports a certified canonical TG prefix on rejection.
  bool tg_cached_root_count = false; // V47: reuse current Candidate Tree terminal count at root.
  bool tg_early_shape_gate = false; // Exact necessary condition on first prefix terminal rows.
  size_t tg_probe_period = 1; // Diagnostic sampling; 1=every eligible state (never changes correctness).
  bool tg_follow_et_auto_pause = false; // Skip TG when ET's online policy is paused.

  size_t tg_prefix_min = 3;       // Experimental: 2 = earlier canonical prefix recognition.
  size_t tg_prefix_cap = 16;      // Bound exact-prefix lookahead, max 64.
  size_t tg_two_min_family = 3;   // Allow 2-path TG only when candidate family has >= this many terminals.
  unsigned tg_batch_mode = 0; // 0=off, 1=count-only, 2=skip placeholders, 3=sparse deferred traversal
  size_t tg_batch_min_ends = 1; // Minimum fully deferred terminal count for a block.
  bool tg_batch_verify_counters = false; // Heavy debug-only per-Find postorder invariant, off in timing.
  bool et_profit_auto = false;      // Optional cost-free fallback to MBET DFS when ET has low measured yield.
  size_t et_auto_window = 4096;     // Full verifier attempts per probe.
  size_t et_auto_pause = 262144;    // Ordinary Find calls between probes.
  size_t et_auto_yield_pct = 3;     // Required new result paths / full checks, percent.
  size_t v51_sample_period = 0; // diagnostic-only: 0=off, sample one Find in N
  size_t v51_max_paths = 64; // stop classification if more than this many terminal paths
  size_t v51_max_cols = 128; // stop classification for large candidate union
  size_t min_left = 1;
  size_t min_right = 1;
  bool emit_stdout = false;
  bool input_swapped = false;
  std::string emit_path;
};

struct MBETFastStats {
  size_t outputs = 0;
  uint64_t checksum_xor = 0;
  uint64_t checksum_sum = 0;
  size_t et_checks = 0;
  uint64_t v56_attempts=0, v56_shape_checked=0, v56_hits=0;
  uint64_t v56_cap_reject=0, v56_outputs=0, v56_pre_fork_skips=0;
  uint64_t v56_pivot_branches=0;
  uint64_t v57_mask_closed=0, v57_mask_candidates=0, v57_mask_output_reject=0;
  uint64_t v57_mask_direct_outputs=0, v57_mask_reused_columns=0;
  uint64_t v58_gate_work_reject=0, v58_gate_spread_reject=0;
  uint64_t v59_dispatch_calls=0, v59_selected_dfs=0;
  uint64_t v59_selected_mask=0, v59_selected_et1=0, v59_selected_et2=0;
  uint64_t v59_mask_hits=0, v59_et1_hits=0, v59_et2_hits=0;
  uint64_t v59_solver_failed=0, v59_legacy_et2_skipped=0;
  uint64_t v60_root_reject=0, v60_early_reject=0;
  uint64_t v61_flat_rows_captured=0, v61_fast_sort_batches=0, v61_fast_emit_batches=0;
  uint64_t v62_tree_mask_nodes=0, v62_tree_mask_leaves=0;
  uint64_t v60_probe_success=0, v60_probe_paths=0;
  uint64_t v60_risk_reject=0, v60_lazy_masks=0;
  uint64_t v58_total_ns=0, v58_shape_ns=0, v58_maskprep_ns=0;
  uint64_t v58_closure_ns=0, v58_emit_ns=0;
  uint64_t v58_mask_prep_calls=0, v58_closure_calls=0, v58_emit_calls=0;

  uint64_t et2_attempts = 0;
  uint64_t et2_verified = 0;
  uint64_t et2_hits = 0;
  uint64_t et2_nonmatching_hits = 0;
  uint64_t et2_fallback_shape = 0;
  uint64_t et2_fallback_degree = 0;
  uint64_t et2_fallback_cap = 0;
  uint64_t et2_mis_generated = 0;
  uint64_t et2_scratch_reused_calls = 0;
  uint64_t et2_root_gate_rejections = 0;
  uint64_t et2_trie_reuse_batches = 0;
  uint64_t et2_trie_reused_columns = 0;
  size_t et_hits = 0;
  size_t et_generated_lower_layers = 0;
  size_t et_auto_skipped_calls = 0;
  size_t et_auto_pauses = 0;
  size_t et_auto_probes = 0;
  uint64_t et_root_gate_reject = 0;
  uint64_t et_scratch_attempts = 0;
  uint64_t tg_family_gate_skips = 0;
  uint64_t tg_shape_gate_reject = 0;
  uint64_t tg_probe_skip = 0;
  uint64_t tg_et_pause_skip = 0;
  // TG v5 does not reorder global vertex IDs. Instead it partitions a
  // canonical prefix of the current candidate-path family when that prefix is
  // already directly resolvable by the matching terminal.
  size_t tg_reordered_nodes = 0;
  uint64_t tg2_plan_attempts = 0, tg2_candidate_prefixes = 0;
  uint64_t tg2_prefix_hits = 0, tg2_nonmatching_hits = 0;
  uint64_t tg2_deferred_paths = 0, tg2_mis_outputs = 0;
  uint64_t tg2_cap_rejections = 0, tg2_emit_new = 0, tg2_emit_duplicate = 0;
  size_t tg_partition_checks = 0;
  size_t tg_partition_hits = 0;
  size_t tg_prefix2_hits = 0;
  size_t tg_two_small_family_skips = 0;
#ifdef MBE_ET13_DIAG
  uint64_t tg_two_hit_family_hist[6]{}; // 3,4,5-7,8-15,16-63,64+ terminal paths
#endif
  size_t tg_prefix_ge3_hits = 0;
  size_t tg_deferred_paths = 0;
  uint64_t tg_batch_blocks = 0;
  uint64_t tg_batch_ends = 0;
  uint64_t tg_batch_nodes = 0;
  uint64_t tg_batch_subcnt_writes = 0;
  uint64_t tg_batch_saved_internal_updates = 0;
  uint64_t tg_batch_saved_ancestor_updates = 0;
  uint64_t tg_batch_elided_result_visits = 0;
  uint64_t tg_batch_singletons = 0;
  uint64_t tg_batch_size_hist[6]{}; // blocks with 1,2,3-4,5-8,9-16,17+ deferred terminals
  uint64_t shared_et_streams = 0;   // Full ET streaming verifications with prefix capture enabled.
  uint64_t shared_prefix_candidates = 0; // ET failures with enough compatible prefix rows.
  uint64_t shared_prefix_used = 0;  // TG accepted previously verified ET prefix (no second exact scan).
  uint64_t shared_paths_reused = 0;
  uint64_t shared_tg_fallbacks = 0; // Normal TG required (no reusable ET prefix).
  uint64_t tg_fused_states = 0;
  uint64_t tg_fused_terminal_visits = 0;
  uint64_t tg_fused_exact_rows = 0;
  uint64_t tg_fused_length_rejected = 0;
  uint64_t tg_profile_samples = 0;
  uint64_t tg_preorder_ns = 0;
  uint64_t tg_planning_ns = 0;
  uint64_t tg_search_resolve_ns = 0;
  size_t tg_gate_attempts = 0;
  size_t tg_metadata_passed = 0;
  size_t tg_length_passed = 0;
  size_t tg_exact_checks = 0;
  size_t tg_five_path_attempts = 0;
  size_t tg_five_path_hits = 0;
};

// Diagnostics are compiled into a separate binary; Release search builds are unaffected.
#ifdef MBE_ET13_DIAG
struct ET13Diagnostics {
  uint64_t try_calls=0, gate_few_paths=0, gate_length=0, gate_cardinality=0, verified=0;
  uint64_t rejected_many_misses=0, rejected_collision=0, rejected_pair=0, rejected_empty_paths=0, rejected_empty_universe=0;
  uint64_t successful=0, matched_edges_total=0, terminal_paths_total=0;
  uint64_t new_result_paths=0, duplicate_result_paths=0, upper_nodes_total=0;
  uint64_t matching_size_buckets[6]{}; // 0,1,2,3,4-7,8+
  uint64_t verified_paths_buckets[5]{}; // 3,4,5-7,8-15,16+
  uint64_t find_calls=0, dfs_find_calls=0, fork_calls=0;
  uint64_t v39_result_ensure_calls=0, v39_result_created_nodes=0, v39_candidate_total_nodes=0;
  uint64_t eligible_wall_ns=0, resolve_wall_ns=0, collect_wall_ns=0;
  uint64_t dfs_pre_nodes=0, dfs_reduce_nodes=0, dfs_result_nodes=0;
  uint64_t fork_nodes_before_reduce=0, fork_remaining_nodes=0, fork_prev_steps=0;
  uint64_t fork_ancestor_probes=0, fork_child_insert_attempts=0;
  uint64_t dfs_end_paths=0, dfs_subcnt_ancestor_updates=0;
  uint64_t profile_samples=0, profile_sample_bounded=0, profile_sample_oversize=0;
  uint64_t profile_matching=0, profile_one_exception=0, profile_other=0;
  uint64_t profile_candidate_paths=0, profile_exception_columns=0;
  uint64_t profile_one_exception_family[5]{}; // 2-3,4-7,8-15,16-31,32+
  uint64_t v52_inline_forks=0, v52_heap_fallback_forks=0;

};
struct ET13TimedRegion {
  using Clock=std::chrono::steady_clock;
  uint64_t &target;
  Clock::time_point start=Clock::now();
  explicit ET13TimedRegion(uint64_t &x):target(x){}
  ~ET13TimedRegion(){target+=std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-start).count();}
};
#endif

// V41: a stateless typed allocator allows the result-tree child vectors to
// share reusable small-allocation blocks without changing vector layout.
// This is only used when MBE_V41_POOLED_RESULT_CHILDREN is enabled.
struct ResultTreeNode;
template <typename T>
struct V41ChildAllocator {
  using value_type = T;
  V41ChildAllocator() noexcept = default;
  template <typename U> V41ChildAllocator(const V41ChildAllocator<U>&) noexcept {}
  [[nodiscard]] T *allocate(std::size_t n) {
    return static_cast<T*>(pool().allocate(n*sizeof(T), alignof(T)));
  }
  void deallocate(T *p, std::size_t n) noexcept {
    pool().deallocate(p, n*sizeof(T), alignof(T));
  }
  static std::pmr::unsynchronized_pool_resource &pool() {
    static std::pmr::unsynchronized_pool_resource r;
    return r;
  }
  template <typename U> bool operator==(const V41ChildAllocator<U>&) const noexcept { return true; }
  template <typename U> bool operator!=(const V41ChildAllocator<U>&) const noexcept { return false; }
};

// v40 experiment: compact ordered children for cache-friendly result/candidate tries.
// Maintains the same ascending order and lookup semantics as std::map.
// This uses binary search for lookups and movable contiguous entries for inserts.
template <typename Node>
class V40FlatChildren {
 public:
  using value_type = std::pair<vid_t, std::unique_ptr<Node>>;
  #if defined(MBE_V41_POOLED_RESULT_CHILDREN)
  using Container = std::conditional_t<std::is_same_v<Node, ResultTreeNode>,
      std::vector<value_type, V41ChildAllocator<value_type>>,
      std::vector<value_type>>;
#else
  using Container = std::vector<value_type>;
#endif
  using iterator = typename Container::iterator;
  using const_iterator = typename Container::const_iterator;
  using reverse_iterator = typename Container::reverse_iterator;
  using const_reverse_iterator = typename Container::const_reverse_iterator;

  iterator begin() noexcept { return data_.begin(); }
  iterator end() noexcept { return data_.end(); }
  const_iterator begin() const noexcept { return data_.begin(); }
  const_iterator end() const noexcept { return data_.end(); }
  reverse_iterator rbegin() noexcept { return data_.rbegin(); }
  reverse_iterator rend() noexcept { return data_.rend(); }
  const_reverse_iterator rbegin() const noexcept { return data_.rbegin(); }
  const_reverse_iterator rend() const noexcept { return data_.rend(); }
  bool empty() const noexcept { return data_.empty(); }
  size_t size() const noexcept { return data_.size(); }
  void clear() noexcept { data_.clear(); }

  iterator lower_bound(vid_t key) {
#if defined(MBE_V41_LINEAR_RESULT_LIMIT) && MBE_V41_LINEAR_RESULT_LIMIT > 0
    if constexpr (std::is_same_v<Node, ResultTreeNode>) {
      if (data_.size() <= MBE_V41_LINEAR_RESULT_LIMIT) {
        auto it = data_.begin();
        while (it != data_.end() && it->first < key) ++it;
        return it;
      }
    }
#endif
    return std::lower_bound(data_.begin(), data_.end(), key,
      [](const value_type &entry, vid_t k) { return entry.first < k; });
  }
  const_iterator lower_bound(vid_t key) const {
#if defined(MBE_V41_LINEAR_RESULT_LIMIT) && MBE_V41_LINEAR_RESULT_LIMIT > 0
    if constexpr (std::is_same_v<Node, ResultTreeNode>) {
      if (data_.size() <= MBE_V41_LINEAR_RESULT_LIMIT) {
        auto it = data_.begin();
        while (it != data_.end() && it->first < key) ++it;
        return it;
      }
    }
#endif
    return std::lower_bound(data_.begin(), data_.end(), key,
      [](const value_type &entry, vid_t k) { return entry.first < k; });
  }
  iterator find(vid_t key) {
    auto it = lower_bound(key);
    return it != data_.end() && it->first == key ? it : data_.end();
  }
  template <typename Arg>
  std::pair<iterator, bool> try_emplace(vid_t key, Arg &&arg) {
    // Monotonically increasing child IDs occur frequently when constructing
    // candidate paths. Skip binary search and avoid shifting existing pairs.
    if (data_.empty() || key > data_.back().first) {
      data_.emplace_back(key, std::forward<Arg>(arg));
      return {std::prev(data_.end()), true};
    }
    if (data_.back().first == key) return {std::prev(data_.end()), false};
    auto it = lower_bound(key);
    if (it != data_.end() && it->first == key) return {it, false};
    return {data_.emplace(it, key, std::forward<Arg>(arg)), true};
  }
  template <typename Arg>
  std::pair<iterator, bool> emplace(vid_t key, Arg &&arg) {
    return try_emplace(key, std::forward<Arg>(arg));
  }
  size_t erase(vid_t key) {
    auto it = find(key);
    if (it == data_.end()) return 0;
    data_.erase(it);
    return 1;
  }
  iterator erase(iterator it) { return data_.erase(it); }
 private:
  Container data_;
};

// V42: allocation-free 0/1-child Result Tree nodes. A 24-byte tagged
// representation keeps a single (key, child) pair in the object; branching
// nodes use a sorted heap buffer with geometric growth. The third word stores
// the number of children, so dynamic capacity is derived as bit_ceil(size).
// Ordering and unique ownership match V40FlatChildren / std::map.
template <typename Node>
class V42InlineChildren {
 public:
  using value_type = std::pair<vid_t, std::unique_ptr<Node>>;
  using iterator = value_type*;
  using const_iterator = const value_type*;
  using reverse_iterator = std::reverse_iterator<iterator>;
  using const_reverse_iterator = std::reverse_iterator<const_iterator>;

  V42InlineChildren() noexcept = default;
  V42InlineChildren(const V42InlineChildren&) = delete;
  V42InlineChildren& operator=(const V42InlineChildren&) = delete;
  V42InlineChildren(V42InlineChildren&&) = delete;
  V42InlineChildren& operator=(V42InlineChildren&&) = delete;
  ~V42InlineChildren() { clear(); }

  iterator begin() noexcept { return data(); }
  iterator end() noexcept { return data()+count_; }
  const_iterator begin() const noexcept { return data(); }
  const_iterator end() const noexcept { return data()+count_; }
  reverse_iterator rbegin() noexcept { return reverse_iterator(end()); }
  reverse_iterator rend() noexcept { return reverse_iterator(begin()); }
  const_reverse_iterator rbegin() const noexcept { return const_reverse_iterator(end()); }
  const_reverse_iterator rend() const noexcept { return const_reverse_iterator(begin()); }
  bool empty() const noexcept { return count_ == 0; }
  size_t size() const noexcept { return count_; }

  iterator lower_bound(vid_t key) noexcept {
    if (count_ <= 1) return count_ && begin()->first < key ? end() : begin();
#ifdef MBE_V61_FAST_RESULT_APPEND
    // The result trie often receives ascending keys in its DFS-driven output.
    // The sorted buffer's last entry is a valid exact lower_bound boundary.
    if constexpr (std::is_same_v<Node, ResultTreeNode>) {
      if (key>=heap_.ptr[count_-1].first)
        return key==heap_.ptr[count_-1].first ? heap_.ptr+count_-1 : heap_.ptr+count_;
    }
#endif
    return std::lower_bound(begin(), end(), key,
      [](const value_type &x, vid_t k){ return x.first < k; });
  }
  const_iterator lower_bound(vid_t key) const noexcept {
    if (count_ <= 1) return count_ && begin()->first < key ? end() : begin();
    return std::lower_bound(begin(), end(), key,
      [](const value_type &x, vid_t k){ return x.first < k; });
  }
  iterator find(vid_t key) noexcept {
    auto it=lower_bound(key);
    return it!=end() && it->first == key ? it : end();
  }
  template<typename Arg>
  std::pair<iterator,bool> try_emplace(vid_t key, Arg&& arg) {
    auto it=lower_bound(key);
    if (it != end() && it->first == key) return {it,false};
    const size_t index=static_cast<size_t>(it-begin());
    value_type item(key, std::forward<Arg>(arg));
    if (count_ == 0) {
      new(inline_slot()) value_type(std::move(item));
      count_=1;
      return {begin(),true};
    }
    if (count_ == 1) {
      value_type* p = allocate(2);
      auto *old=inline_slot();
      if (index==0) {
        new(p) value_type(std::move(item));
        new(p+1) value_type(std::move(*old));
      } else {
        new(p) value_type(std::move(*old));
        new(p+1) value_type(std::move(item));
      }
      old->~value_type();
      // Pointer storage overlaps the now-destroyed in-object singleton.
      heap_.ptr=p;
      heap_.capacity=2;
      count_=2;
      return {p+index,true};
    }
    value_type* p=heap_.ptr;
    const size_t cap=heap_.capacity;
    if (count_ == cap) {
      value_type* q=allocate(cap*2);
      for (size_t i=0;i<index;i++) new(q+i) value_type(std::move(p[i]));
      new(q+index) value_type(std::move(item));
      for (size_t i=index;i<count_;i++) new(q+i+1) value_type(std::move(p[i]));
      destroy_range(p,count_);
      deallocate(p,cap);
      heap_.ptr=q;
      heap_.capacity=cap*2;
    } else {
      if (index==count_) {
        new(p+count_) value_type(std::move(item));
      } else {
        new(p+count_) value_type(std::move(p[count_-1]));
        for (size_t i=count_-1;i>index;i--) p[i]=std::move(p[i-1]);
        p[index]=std::move(item);
      }
    }
    ++count_;
    return {heap_.ptr+index,true};
  }
  template<typename Arg>
  std::pair<iterator,bool> emplace(vid_t key, Arg&& arg) {
    return try_emplace(key,std::forward<Arg>(arg));
  }
  iterator erase(iterator it) {
    size_t index=static_cast<size_t>(it-begin());
    assert(index<count_);
    if (count_==1) {
      inline_slot()->~value_type();
      count_=0;
      return begin();
    }
    value_type* p=heap_.ptr;
    for(size_t i=index;i+1<count_;++i) p[i]=std::move(p[i+1]);
    p[count_-1].~value_type();
    if (count_==2) {
      // Convert two-element heap storage back to the inline singleton.
      value_type remaining(std::move(p[0]));
      p[0].~value_type();
      deallocate(p,heap_.capacity);
      new(inline_slot()) value_type(std::move(remaining));
      count_=1;
      return index==0 ? begin() : end();
    }
    --count_;
    return begin()+index;
  }
  size_t erase(vid_t key) {
    auto it=find(key);
    if (it==end()) return 0;
    erase(it);
    return 1;
  }
  void clear() noexcept {
    if (count_==1) inline_slot()->~value_type();
    else if (count_>=2) {
      auto* p=heap_.ptr;
      destroy_range(p,count_);
      deallocate(p,heap_.capacity);
    }
    count_=0;
  }
 private:
  // The inline singleton uses the first 16 bytes; a dynamic array pointer
  // uses the first 8. This avoids the 8-byte/node overhead of std::variant.
  union { struct { alignas(value_type) unsigned char bytes[sizeof(value_type)]; } one_; struct { value_type* ptr; size_t capacity; } heap_; };
  size_t count_=0;
  value_type* inline_slot() noexcept { return reinterpret_cast<value_type*>(one_.bytes); }
  const value_type* inline_slot() const noexcept { return reinterpret_cast<const value_type*>(one_.bytes); }
  value_type* data() noexcept { return count_>=2 ? heap_.ptr : inline_slot(); }
  const value_type* data() const noexcept { return count_>=2 ? heap_.ptr : inline_slot(); }
  static size_t capacity(size_t n) noexcept {
    size_t v=2;
    while(v<n) v*=2;
    return v;
  }
  static value_type* allocate(size_t n) {
#ifdef MBE_V42_INLINE_POOL
    return static_cast<value_type*>(V41ChildAllocator<value_type>::pool().allocate(n*sizeof(value_type),alignof(value_type)));
#else
    return std::allocator<value_type>().allocate(n);
#endif
  }
  static void deallocate(value_type* p,size_t n) noexcept {
#ifdef MBE_V42_INLINE_POOL
    V41ChildAllocator<value_type>::pool().deallocate(p,n*sizeof(value_type),alignof(value_type));
#else
    std::allocator<value_type>().deallocate(p,n);
#endif
  }
  static void destroy_range(value_type* p,size_t n) noexcept {
    for(size_t i=0;i<n;i++) p[i].~value_type();
  }
};
static_assert(sizeof(V42InlineChildren<ResultTreeNode>) == 24,
              "V42 inline children must remain 24 bytes");

struct ResultTreeNode {
  explicit ResultTreeNode() : is_end(false), has_prev(false) {}

  ~ResultTreeNode() {
    for (auto &[k, v] : children) v.reset();
  }

  #ifdef MBE_V42_INLINE_RESULT
  V42InlineChildren<ResultTreeNode> children;
  #elif defined(MBE_V40_FLAT_RESULT)
  V40FlatChildren<ResultTreeNode> children;
#else
  std::map<vid_t, std::unique_ptr<ResultTreeNode>> children;
#endif
#ifdef MBE_V31_RESULT_HOT
  // Parent-local last-child cache. Map insertions do not invalidate node addresses.
  vid_t hot_key = 0;
  ResultTreeNode *hot_child = nullptr;
#endif
#ifdef MBE_V32_RESULT_POOL
  // Fixed-size recyclable allocations. Does not pool std::map RB-tree entries.
  static std::pmr::unsynchronized_pool_resource &pool() {
    static std::pmr::unsynchronized_pool_resource p;
    return p;
  }
  static void *operator new(std::size_t n) { return pool().allocate(n, alignof(ResultTreeNode)); }
  static void operator delete(void *p) noexcept { pool().deallocate(p, sizeof(ResultTreeNode), alignof(ResultTreeNode)); }
  static void operator delete(void *p, std::size_t) noexcept { pool().deallocate(p, sizeof(ResultTreeNode), alignof(ResultTreeNode)); }
#endif
  bool is_end;
  bool has_prev;
};

struct NeighborTreeNode {
  explicit NeighborTreeNode(vid_t id, NeighborTreeNode *pa)
      : vid(id), is_end(false), is_res(false), is_use(false), tg_deferred(false),
        sub_cnt(0), end_count(0),
        min_end_len(std::numeric_limits<size_t>::max()), max_end_len(0),
        prev(nullptr), fork(nullptr), parent(pa) {}

  ~NeighborTreeNode() {
    for (auto &[k, v] : children) v.reset();
  }

  vid_t vid;
  #ifdef MBE_V63_INLINE_CANDIDATE
  V42InlineChildren<NeighborTreeNode> children;
  #elif defined(MBE_V40_FLAT_CANDIDATE)
  V40FlatChildren<NeighborTreeNode> children;
#else
  std::map<vid_t, std::unique_ptr<NeighborTreeNode>> children;
#endif
#ifdef MBE_V32_CANDIDATE_POOL
  static std::pmr::unsynchronized_pool_resource &pool() {
    static std::pmr::unsynchronized_pool_resource p;
    return p;
  }
  static void *operator new(std::size_t n) { return pool().allocate(n, alignof(NeighborTreeNode)); }
  static void operator delete(void *p) noexcept { pool().deallocate(p, sizeof(NeighborTreeNode), alignof(NeighborTreeNode)); }
  static void operator delete(void *p, std::size_t) noexcept { pool().deallocate(p, sizeof(NeighborTreeNode), alignof(NeighborTreeNode)); }
#endif
  bool is_end;
  bool is_res;
  bool is_use;
  bool tg_deferred;
  size_t sub_cnt;
  size_t end_count;
  size_t min_end_len;
  size_t max_end_len;
  NeighborTreeNode *prev;
  std::pair<size_t, size_t> dfs_idx;
  NeighborTreeNode *fork;
  NeighborTreeNode *parent;

  friend std::ostream &operator<<(std::ostream &os, const NeighborTreeNode &n) {
    os << "[";
    os << "&=" << &n << ", ";
    os << "vid=" << n.vid << ", ";
    os << "children=(";
    for (const auto &[id, child] : n.children) {
      os << id << ",";
    }
    os << "), ";
    os << "is_end=" << n.is_end << ", ";
    os << "sub_cnt=" << n.sub_cnt << ", ";
    os << "prev=" << n.prev << ", ";
    os << "dfs_idx=" << n.dfs_idx.first << "|" << n.dfs_idx.second << ", ";
    return os;
  }
};

#ifdef MBE_V31_FORK_PATH
// Non-owning view of the current Find() DFS path; no per-fork path copy.
struct V31PathView {
  const std::vector<NeighborTreeNode *> &storage;
  size_t offset, length;
  NeighborTreeNode *operator[](size_t i) const { return storage[offset + i]; }
  NeighborTreeNode *back() const { return storage[offset + length - 1]; }
  auto begin() const { return storage.begin() + offset; }
  auto end() const { return storage.begin() + offset + length; }
};
#endif

class MBETFast {
 public:
  explicit MBETFast(BiGraph bi_graph, MBETFastConfig config = {})
      : config_(std::move(config)), bi_graph_(std::move(bi_graph)),
        swap_vertices_(config_.input_swapped), bic_cnt_(0) {}

  const MBETFastStats &Stats() const { return stats_; }
  uint64_t ForkPathStepsReused() const { return v31_fork_path_steps_reused_; }
  uint64_t ResultHotHits() const { return v31_result_hot_hits_; }
#ifdef MBE_ET13_DIAG
  const ET13Diagnostics &ETDiag() const {return et13_;}
#endif


  std::tuple<size_t, double, std::map<std::string, double>> Run() {
    main_watch_.Start();
    std::map<std::string, double> times;
    auto run_watch = RunTimer::StopWatch();

    {
      // renumber V
      std::vector<std::pair<vid_t, size_t>> Vs;
      for (auto &v : bi_graph_.VerticesV()) {
        Vs.emplace_back(v->vid, v->neighbors.size());
      }
      // Keep the native MBET global non-increasing-degree order unchanged.
      // TG v5 acts only inside a recursive candidate-tree state; it never
      // renumbers/reorders global lower-side vertices, so result-tree
      // reclamation and canonical visiting order remain identical to TG-off.
      std::sort(Vs.begin(), Vs.end(), [](const auto &a, const auto &b) {
        return a.second > b.second || (a.second == b.second && a.first < b.first);
      });

      for (size_t i = 0; i < Vs.size(); i++) bi_graph_.VertexV(Vs[i].first)->vid = i;
      std::sort(bi_graph_.VerticesV().begin(), bi_graph_.VerticesV().end(),
                [](const std::shared_ptr<Vertex> &a, const std::shared_ptr<Vertex> &b) { return a->vid < b->vid; });
      for (auto &u : bi_graph_.VerticesU()) {
        std::sort(u->neighbors.begin(), u->neighbors.end(),
                  [](const std::shared_ptr<Vertex> &a, const std::shared_ptr<Vertex> &b) { return a->vid < b->vid; });
      }
    }
    {
      // renumber U
      std::vector<std::pair<vid_t, size_t>> Us;
      for (auto &u : bi_graph_.VerticesU()) {
        Us.emplace_back(u->vid, u->neighbors.size());
      }
      std::sort(Us.begin(), Us.end(), [](const auto &a, const auto &b) {
        return a.second > b.second || (a.second == b.second && a.first < b.first);
      });
      for (size_t i = 0; i < Us.size(); i++) bi_graph_.VertexU(Us[i].first)->vid = i;
      std::sort(bi_graph_.VerticesU().begin(), bi_graph_.VerticesU().end(),
                [](const std::shared_ptr<Vertex> &a, const std::shared_ptr<Vertex> &b) { return a->vid < b->vid; });
      for (auto &v : bi_graph_.VerticesV()) {
        std::sort(v->neighbors.begin(), v->neighbors.end(),
                  [](const std::shared_ptr<Vertex> &a, const std::shared_ptr<Vertex> &b) { return a->vid < b->vid; });
      }
    }

    times.emplace("sort", run_watch.Stop());
    run_watch.Report("MBET::Pre-sort");
    run_watch.Start();

    bic_cnt_ = 0;
    duplicated_cnt_ = 0;
    cand_tree_cnt_ = 0;
    result_tree_size_ = 0;
    result_tree_cnt_ = 0;
    cand_tree_size_cur_ = 0;
    cand_tree_size_max_ = 0;
    cand_tree_size_total_ = 0;
    result_tree_size_cur_ = 0;
    result_tree_size_max_ = 0;
    result_tree_size_total_ = 0;
    stats_ = {};
#ifdef MBE_ET13_DIAG
    et13_ = {};
#endif
#ifdef MBE_V29_PROFILE
    v29_dfs_find_calls_=v29_dfs_find_end_paths_=v29_fork_calls_=0;
    v29_fork_depth_sum_=v29_fork_depth_max_=v29_root_builds_=0;
    v29_output_calls_=v29_compressed_blocks_scanned_=v29_compressed_blocks_emitted_=0;
#endif
    tg_scratch_current_.clear();
    tg_scratch_first_.clear();
    tg_scratch_misses_.clear();
    // ST v13: free depth slots between independent Run() calls.
    st_intersection_scratch_.clear();
    // TG v5 never changes the global MBET ordering.
    stats_.tg_reordered_nodes = 0;
    checksum_out_.close();
    if (!config_.emit_path.empty()) checksum_out_.open(config_.emit_path);

    result_tree_roots_.resize(bi_graph_.VerticesV().size());
    traverse_order_u_.resize(bi_graph_.VerticesU().size());
    for (size_t i = 0; i < traverse_order_u_.size(); i++) traverse_order_u_[i] = i;
    traverse_order_u_tmp_.resize(bi_graph_.VerticesU().size());
    traverse_order_nbr_cnt_.resize(bi_graph_.VerticesV().size(), 0);
    traverse_order_v_range_.resize(bi_graph_.VerticesV().size());
    traverse_order_v_range_begin_.resize(bi_graph_.VerticesV().size(), 0);
    cand_tree_prev_node_.assign(bi_graph_.VerticesV().size(), {0, nullptr});
    result_tree_prev_dfs_idx_.assign(bi_graph_.VerticesV().size(), {0, 0});
    cache_inter_neighbors_.resize(bi_graph_.VerticesV().size());
    init_inter_neighbors_.resize(bi_graph_.VerticesV().size(), {(vid_t)-1, {}});

    std::vector<std::vector<size_t>> traverse_order_pre_pos(bi_graph_.VerticesV().size());
    for (auto &v : bi_graph_.VerticesV()) traverse_order_pre_pos[v->vid].reserve(v->neighbors.size());
    std::vector<std::pair<vid_t, NeighborTreeNode *>> traverse_order_last_node(bi_graph_.VerticesU().size(),
                                                                               {-1, nullptr});
    std::vector<size_t> traverse_order_depth_cnt(bi_graph_.VerticesU().size(), 0);

    build_traverse_order(0, traverse_order_u_.size(), 0);

    times.emplace("order", run_watch.Stop());
    run_watch.Report("MBET::Run-order");
    run_watch.Start();

    result_tree_root_vid_ = 0;
#ifndef ONLY_COUNTING
    VidList R;
    R.reserve(bi_graph_.VerticesU().front()->neighbors.size());
    std::vector<std::pair<vid_t, CompressedNeighbors>> CLs;
    auto update_compressed_root_neighbors = [&](vid_t root_id) {
      auto watch = DebugTimer<104>::AutoWatch();

      if (!CLs.empty() && CLs.front().first == root_id) {
        return;
      }
      CLs.resize(1);
      CLs.front().first = root_id;
      auto &CL = CLs.front().second;
      CL.clear();
      size_t num = bi_graph_.VertexV(root_id)->neighbors.size();
      size_t cnt = 0;
      while (num >= NumBits) {
        CL.emplace_back(cnt, -1);
        cnt++;
        num -= NumBits;
      }
      if (num > 0) {
        CL.emplace_back(cnt, 0);
        while (num > 0) {
          CL.back().second = (CL.back().second << 1) | 1;
          num--;
        }
      }
    };
#ifndef MBETM
    auto update_compressed_neighbors = [&](size_t pos, vid_t vid) {
      auto watch = DebugTimer<104>::AutoWatch();

      if (CLs.size() > pos && CLs[pos].first == vid) {
        return;
      }
      CLs.resize(pos + 1);
      CLs[pos].first = vid;
      auto &CPL = CLs[pos - 1].second;
      auto &CL = CLs[pos].second;
      CL.clear();
      if (init_inter_neighbors_[vid].first != result_tree_root_vid_) {
        init_inter_neighbors_[vid].first = result_tree_root_vid_;
        init_inter_neighbors_[vid].second.clear();
      }
      if (init_inter_neighbors_[vid].second.empty()) {
        auto auto_watch = DebugTimer<31>::AutoWatch();

        auto &root_nbrs = bi_graph_.VertexV(result_tree_root_vid_)->neighbors;
        auto &nbrs = bi_graph_.VertexV(vid)->neighbors;
        auto nit = nbrs.begin();
        for (auto [idx, cpn] : CPL) {
          size_t tmp = 0;
          while (cpn > 0) {
            auto ctz = __builtin_ctzl(cpn);
            auto nbr_vid = root_nbrs[idx * NumBits + ctz]->vid;
            while (nit != nbrs.end() && (*nit)->vid < nbr_vid) nit++;
            if (nit == nbrs.end()) break;
            auto low_bit = cpn & (-cpn);
            if ((*nit)->vid == nbr_vid) {
              tmp |= low_bit;
            }
            cpn ^= low_bit;
          }
          if (tmp != 0) {
            CL.emplace_back(idx, tmp);
          }
          if (nit == nbrs.end()) break;
        }
      } else {
        auto auto_watch = DebugTimer<32>::AutoWatch();

        auto &cnbrs = init_inter_neighbors_[vid].second;
        auto cnit = cnbrs.begin();
        for (const auto &[idx, cpn] : CPL) {
          while (cnit != cnbrs.end() && cnit->first < idx) cnit++;
          if (cnit == cnbrs.end()) break;
          if (cnit->first == idx) {
            size_t tmp = cnit->second & cpn;
            if (tmp > 0) {
              CL.emplace_back(idx, tmp);
            }
          }
        }
      }
    };
    if (config_.st) update_compressed_root_neighbors(result_tree_root_vid_);
#endif
#endif
    for (traverse_order_u_pos_ = 0; traverse_order_u_pos_ < traverse_order_u_.size(); traverse_order_u_pos_++) {
      if (traverse_order_u_tmp_[traverse_order_u_pos_] ==
          static_cast<decltype(traverse_order_u_tmp_)::value_type>(-1)) {
        continue;
      }
      auto &u = bi_graph_.VertexU(traverse_order_u_[traverse_order_u_pos_]);
#ifndef MBETM
      while (result_tree_root_vid_ < u->neighbors.front()->vid) {
        if (result_tree_roots_[result_tree_root_vid_]) {
          result_tree_size_ = 0;
#ifndef ONLY_COUNTING
          if (config_.st) {
            auto auto_watch = DebugTimer<102>::AutoWatch();
            result_tree_cnt_++;
            dfs_cnt_ = 0;
            dfs_result_tree(result_tree_roots_[result_tree_root_vid_].get(), result_tree_root_vid_, 0);
          }
          {
            auto auto_watch = DebugTimer<103>::AutoWatch();
            R.clear();
            if (config_.st) {
              Enumerate(result_tree_roots_[result_tree_root_vid_].get(), result_tree_root_vid_, CLs.front().second, R, 0);
            } else {
              VidList upper;
              EnumeratePlain(result_tree_roots_[result_tree_root_vid_].get(), result_tree_root_vid_, upper, R);
            }
          }
#endif
          result_tree_roots_[result_tree_root_vid_].reset();
          result_tree_size_max_ = std::max(result_tree_size_max_, result_tree_size_cur_);
          result_tree_size_cur_ -= result_tree_size_;
          result_tree_size_total_ += result_tree_size_;
        }
        result_tree_root_vid_++;
#ifndef ONLY_COUNTING
        if (result_tree_root_vid_ < bi_graph_.VerticesV().size()) {
          if (config_.st) update_compressed_root_neighbors(result_tree_root_vid_);
        }
#endif
      }
      if (result_tree_roots_[result_tree_root_vid_]) {
        auto rnode = result_tree_roots_[result_tree_root_vid_].get();
#ifndef ONLY_COUNTING
        R.clear();
        R.emplace_back(result_tree_root_vid_);
#endif
        for (size_t ni = 1; ni < u->neighbors.size(); ni++) {
          auto it = rnode->children.begin();
          while (it != rnode->children.end()) {
            if (it->first >= u->neighbors[ni]->vid) {
              break;
            }
            result_tree_size_ = 0;
#ifndef ONLY_COUNTING
            if (config_.st) {
              auto auto_watch = DebugTimer<102>::AutoWatch();
              result_tree_cnt_++;
              dfs_cnt_ = 0;
              dfs_result_tree(it->second.get(), it->first, 0);
            }
            {
              auto auto_watch = DebugTimer<103>::AutoWatch();
              if (config_.st) {
                Enumerate(it->second.get(), it->first, CLs[ni - 1].second, R, 0);
              } else {
                VidList upper = ComputeUpperForLower(R);
                EnumeratePlain(it->second.get(), it->first, upper, R);
              }
            }
#endif
#ifdef MBE_V31_RESULT_HOT
            rnode->hot_child = nullptr;
#endif
            it = rnode->children.erase(it);
            result_tree_size_max_ = std::max(result_tree_size_max_, result_tree_size_cur_);
            result_tree_size_cur_ -= result_tree_size_;
            result_tree_size_total_ += result_tree_size_;
          }
          if (it == rnode->children.end() || it->first > u->neighbors[ni]->vid) {
            break;
          }
          rnode = it->second.get();
#ifndef ONLY_COUNTING
          if (config_.st) update_compressed_neighbors(ni, it->first);
          R.emplace_back(it->first);
#endif
        }
      }
      {
        auto rnode = result_tree_roots_[u->neighbors.front()->vid].get();
        auto is_new = (rnode == nullptr);
        if (!is_new) {
          for (size_t ni = 1; ni < u->neighbors.size(); ni++) {
            if (rnode->children.empty() || rnode->children.begin()->first > u->neighbors[ni]->vid) {
              is_new = true;
              break;
            }
            rnode = rnode->children.begin()->second.get();
          }
          is_new |= !rnode->is_end;
        }
        if (!is_new) {
          for (auto &v : u->neighbors) {
            traverse_order_pre_pos[v->vid].emplace_back(traverse_order_u_pos_);
          }
          continue;
        }
      }
#endif
#ifdef MBE_V29_PROFILE
      ++v29_root_builds_;
#endif
      auto cand_tree_root = std::make_unique<NeighborTreeNode>(-1, nullptr);
      size_t nbr_tree_size = 1;
      {
        auto auto_watch = DebugTimer<100>::AutoWatch();

        std::vector<vid_t> X;
        for (auto &v : u->neighbors) {
          for (auto &uu_pos : traverse_order_pre_pos[v->vid]) {
            auto uu = traverse_order_u_[uu_pos];
            NeighborTreeNode *parent_node = nullptr;
            if (traverse_order_last_node[uu].first != traverse_order_u_pos_) {
              traverse_order_last_node[uu] = {traverse_order_u_pos_, cand_tree_root.get()};
              traverse_order_depth_cnt[uu] = 0;
            } else {
              parent_node = traverse_order_last_node[uu].second;
              parent_node->sub_cnt--;
            }
            auto [it, res] = traverse_order_last_node[uu].second->children.try_emplace(v->vid, nullptr);
            if (res) {
              it->second = std::make_unique<NeighborTreeNode>(v->vid, parent_node);
              nbr_tree_size++;
            }
            it->second->sub_cnt++;
            traverse_order_last_node[uu].second = it->second.get();
            if (++traverse_order_depth_cnt[uu] == u->neighbors.size()) {
              X.emplace_back(uu);
              if (uu_pos > 0) {
                auto pos = uu_pos - 1;
                while (pos > 0) {
                  if (traverse_order_u_tmp_[pos] != static_cast<decltype(traverse_order_u_tmp_)::value_type>(-1)) {
                    break;
                  }
                  X.emplace_back(traverse_order_u_[pos]);
                  pos--;
                }
                if (traverse_order_u_tmp_[pos] == static_cast<decltype(traverse_order_u_tmp_)::value_type>(-1)) {
                  X.emplace_back(traverse_order_u_[pos]);
                }
              }
            }
          }
          traverse_order_pre_pos[v->vid].emplace_back(traverse_order_u_pos_);
        }
        if (!X.empty()) {
          auto node = traverse_order_last_node[X.front()].second;
          node->sub_cnt = 0;
          while (node->sub_cnt == 0) {
            auto np = node->parent;
            if (!np) {
              cand_tree_root->children.erase(node->vid);
              nbr_tree_size--;
              break;
            }
            auto next_it = np->children.erase(np->children.begin());
            nbr_tree_size--;
            if (next_it != np->children.end()) {
              break;
            }
            node = np;
          }
        }
#ifdef ONLY_COUNTING
        bic_cnt_++;
        if (bic_cnt_ % 1000000 == 0) {
          std::cout << "[DBG] cnt=" << bic_cnt_ << " time=" << main_watch_.Stop() << std::endl;

          std::ifstream status("/proc/self/status");
          for (std::string line; std::getline(status, line);) {
            if (line.rfind("VmPeak:", 0) == 0) {
              std::cout << " [MEMORY] VmPeak: " << std::stod(line.substr(7)) / 1024.0 << "MB" << std::endl;
            }
            if (line.rfind("VmSize:", 0) == 0) {
              std::cout << " [MEMORY] VmSize: " << std::stod(line.substr(7)) / 1024.0 << "MB" << std::endl;
            }
            if (line.rfind("VmHWM:", 0) == 0) {
              std::cout << " [MEMORY] VmHWM: " << std::stod(line.substr(6)) / 1024.0 << "MB" << std::endl;
            }
            if (line.rfind("VmRSS:", 0) == 0) {
              std::cout << " [MEMORY] VmRSS: " << std::stod(line.substr(6)) / 1024.0 << "MB" << std::endl;
            }
          }

          std::cout << " [STAT] duplicated_cnt=" << duplicated_cnt_ << std::endl;
          std::cout << " [STAT] cand_tree_size_cur=" << cand_tree_size_cur_ << std::endl;
          std::cout << " [STAT] cand_tree_size_max=" << cand_tree_size_max_ << std::endl;
          std::cout << " [STAT] cand_tree_size_total=" << cand_tree_size_total_ << std::endl;
          std::cout << " [STAT] result_tree_size_cur=" << result_tree_size_cur_ << std::endl;
          std::cout << " [STAT] result_tree_size_max=" << result_tree_size_max_ << std::endl;
          std::cout << " [STAT] result_tree_size_total=" << result_tree_size_total_ << std::endl;
        }
#else
        X.emplace_back(u->vid);
        VidList Y(u->neighbors.size());
        for (size_t i = 0; i < u->neighbors.size(); i++) Y[i] = u->neighbors[i]->vid;
        if (traverse_order_u_pos_ > 0) {
          auto pos = traverse_order_u_pos_ - 1;
          while (pos > 0) {
            if (traverse_order_u_tmp_[pos] != static_cast<decltype(traverse_order_u_tmp_)::value_type>(-1)) {
              break;
            }
            X.emplace_back(traverse_order_u_[pos]);
            pos--;
          }
          if (traverse_order_u_tmp_[pos] == static_cast<decltype(traverse_order_u_tmp_)::value_type>(-1)) {
            X.emplace_back(traverse_order_u_[pos]);
          }
        }
        Report(X, Y);
#endif
        cand_tree_size_total_ += nbr_tree_size;
        cand_tree_size_cur_ += nbr_tree_size;
        cand_tree_size_max_ = std::max(cand_tree_size_max_, cand_tree_size_cur_);
        for (auto &[id, child] : cand_tree_root->children) {
          build_end(child.get());
          if (config_.et) {
            cand_tree_root->end_count += child->end_count;
            // V50: the original initial-tree builder accumulated only the
            // root count. Complete the root length summary as well; recursive
            // candidates already maintain all three fields in dfs_reduce.
            if (child->end_count) {
              cand_tree_root->min_end_len = std::min(
                  cand_tree_root->min_end_len, child->min_end_len + 1);
              cand_tree_root->max_end_len = std::max(
                  cand_tree_root->max_end_len, child->max_end_len + 1);
            }
          }
        }
      }
      {
        auto auto_watch = DebugTimer<101>::AutoWatch();

        Find(std::move(cand_tree_root));
        cand_tree_size_cur_ -= nbr_tree_size;
      }
#ifdef MBETM
      {
        for (auto &v : u->neighbors) {
          if (!result_tree_roots_[v->vid]) {
            continue;
          }
          result_tree_size_ = 0;
#ifndef ONLY_COUNTING
          result_tree_root_vid_ = v->vid;
          {
            auto auto_watch = DebugTimer<102>::AutoWatch();

            result_tree_cnt_++;
            dfs_cnt_ = 0;
            dfs_result_tree(result_tree_roots_[result_tree_root_vid_].get(), result_tree_root_vid_, 0);
          }
          if (config_.st) update_compressed_root_neighbors(result_tree_root_vid_);
          {
            auto auto_watch = DebugTimer<103>::AutoWatch();

            R.clear();
            if (config_.st) {
              Enumerate(result_tree_roots_[result_tree_root_vid_].get(), result_tree_root_vid_, CLs.front().second, R, 0);
            } else {
              VidList upper;
              EnumeratePlain(result_tree_roots_[result_tree_root_vid_].get(), result_tree_root_vid_, upper, R);
            }
          }
#endif
          result_tree_roots_[v->vid].reset();
          result_tree_size_max_ = std::max(result_tree_size_max_, result_tree_size_cur_);
          result_tree_size_cur_ -= result_tree_size_;
          result_tree_size_total_ += result_tree_size_;
        }
      }
#endif
    }
#ifndef MBETM
    while (result_tree_root_vid_ < bi_graph_.VerticesV().size()) {
      if (result_tree_roots_[result_tree_root_vid_]) {
        result_tree_size_ = 0;
#ifndef ONLY_COUNTING
        if (config_.st) {
          auto auto_watch = DebugTimer<102>::AutoWatch();
          result_tree_cnt_++;
          dfs_cnt_ = 0;
          dfs_result_tree(result_tree_roots_[result_tree_root_vid_].get(), result_tree_root_vid_, 0);
        }
        {
          auto auto_watch = DebugTimer<103>::AutoWatch();
          R.clear();
          if (config_.st) {
            Enumerate(result_tree_roots_[result_tree_root_vid_].get(), result_tree_root_vid_, CLs.front().second, R, 0);
          } else {
            VidList upper;
            EnumeratePlain(result_tree_roots_[result_tree_root_vid_].get(), result_tree_root_vid_, upper, R);
          }
        }
#endif
        result_tree_roots_[result_tree_root_vid_].reset();
        result_tree_size_max_ = std::max(result_tree_size_max_, result_tree_size_cur_);
        result_tree_size_cur_ -= result_tree_size_;
        result_tree_size_total_ += result_tree_size_;
      }
      result_tree_root_vid_++;
#ifndef ONLY_COUNTING
      if (result_tree_root_vid_ < bi_graph_.VerticesV().size() && config_.st) {
        update_compressed_root_neighbors(result_tree_root_vid_);
      }
#endif
    }
#endif

    times.emplace("run", run_watch.Stop());
    run_watch.Report("MBET::Run");

    stats_.outputs = bic_cnt_;
#ifdef MBE_V29_PROFILE
    std::cout << "[V29_COUNTER] dfs_find_calls=" << v29_dfs_find_calls_
              << " dfs_find_end_paths=" << v29_dfs_find_end_paths_
              << " fork_calls=" << v29_fork_calls_
              << " fork_depth_sum=" << v29_fork_depth_sum_
              << " fork_depth_max=" << v29_fork_depth_max_
              << " root_candidate_builds=" << v29_root_builds_
              << " cand_nodes_total=" << cand_tree_size_total_
              << " cand_nodes_peak=" << cand_tree_size_max_
              << " result_nodes_total=" << result_tree_size_total_
              << " result_nodes_peak=" << result_tree_size_max_
              << " duplicate_inserts=" << duplicated_cnt_
              << " outputs=" << v29_output_calls_
              << " intersection_input_blocks=" << v29_compressed_blocks_scanned_
              << " intersection_output_blocks=" << v29_compressed_blocks_emitted_
              << "\n";
#define V29_REPORT(ID, LABEL) do { std::cout << "[V29_PHASE] "; DebugTimer<ID>::Report(LABEL); } while(0)
    V29_REPORT(100, "RootCandidateBuild");
    V29_REPORT(101, "RootFind_inclusive");
    V29_REPORT(11, "CandidateDFSPre");
    V29_REPORT(12, "ResultTreeInsert");
    V29_REPORT(13, "CandidateSubcntUpdate");
    V29_REPORT(14, "ForkConstruct");
    V29_REPORT(15, "ForkPrune");
    V29_REPORT(16, "ForkDFSReduce");
    V29_REPORT(102, "ResultTreeDFSPre");
    V29_REPORT(103, "ResultTreeEnumerate_inclusive");
    V29_REPORT(21, "ResultInitialIntersection");
    V29_REPORT(31, "IntersectionScalar");
    V29_REPORT(32, "IntersectionCompressed");
    V29_REPORT(33, "IntersectionCachePush");
    V29_REPORT(34, "IntersectionCachePop");
    V29_REPORT(40, "HandleOutput");
    V29_REPORT(41, "ETTry_inclusive");
    V29_REPORT(42, "TGPlan_inclusive");
    V29_REPORT(43, "MISResolve_inclusive");
    V29_REPORT(44, "MISAppendColumn");
    V29_REPORT(104, "CompressedRootOrUpdate");
#undef V29_REPORT
#endif
    return {bic_cnt_, main_watch_.Stop(), times};
  }

 private:
  static uint64_t SplitMix64(uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
  }

  uint64_t HashSide(const VidList &ids, bool upper_side) const {
    uint64_t a = 0x243f6a8885a308d3ULL;
    uint64_t b = 0x13198a2e03707344ULL;
    for (auto id : ids) {
      uint64_t label = upper_side ? bi_graph_.VertexU(id)->label : bi_graph_.VertexV(id)->label;
      uint64_t h = SplitMix64(label + 0x100000001b3ULL);
      a += h;
      b ^= (h << (label & 31)) | (h >> ((64 - (label & 31)) & 63));
    }
    return SplitMix64(a ^ SplitMix64(b + ids.size()));
  }

  void HandleOutput(const VidList &upper, const VidList &lower) {
#ifdef MBE_V29_PROFILE
    auto v29_out_watch = DebugTimer<40>::AutoWatch();
    ++v29_output_calls_;
#endif
    const size_t left_sz = swap_vertices_ ? lower.size() : upper.size();
    const size_t right_sz = swap_vertices_ ? upper.size() : lower.size();
    if (left_sz < config_.min_left || right_sz < config_.min_right) return;

    bic_cnt_++;
    uint64_t hu = HashSide(upper, true);
    uint64_t hl = HashSide(lower, false);
    uint64_t hleft = swap_vertices_ ? hl : hu;
    uint64_t hright = swap_vertices_ ? hu : hl;
    uint64_t hb = SplitMix64(SplitMix64(hleft + 0x6a09e667f3bcc909ULL) ^
                             SplitMix64(hright + 0xbb67ae8584caa73bULL));
    stats_.checksum_xor ^= hb;
    stats_.checksum_sum += hb;

    if (config_.emit_stdout || checksum_out_.is_open()) {
      std::ostream &out = config_.emit_stdout ? std::cout : checksum_out_;
      auto emit_side = [&](const VidList &ids, bool upper_side) {
        out << '[';
        bool first = true;
        for (auto id : ids) {
          if (!first) out << ',';
          first = false;
          out << (upper_side ? bi_graph_.VertexU(id)->label : bi_graph_.VertexV(id)->label);
        }
        out << ']';
      };
      if (!swap_vertices_) {
        emit_side(upper, true); emit_side(lower, false);
      } else {
        emit_side(lower, false); emit_side(upper, true);
      }
      out << '\n';
    }
  }

  void Report(const VidList &L, const VidList &R) { HandleOutput(L, R); }

#ifdef MBE_V42_FAST_REPORT
  // Hash the compressed left side directly, without materializing a VidList.
  // The right-side hash is already maintained in O(1) per DFS edge.
  // Output-emitting and exact-oracle modes retain the original slow path.
  struct V42HashState {
    uint64_t a = 0x243f6a8885a308d3ULL;
    uint64_t b = 0x13198a2e03707344ULL;
    size_t size = 0;
    void add(uint64_t label) {
      uint64_t h = SplitMix64(label + 0x100000001b3ULL);
      a += h;
      b ^= (h << (label & 31)) | (h >> ((64 - (label & 31)) & 63));
      ++size;
    }
    uint64_t finish() const { return SplitMix64(a ^ SplitMix64(b + size)); }
  };
  void ReportFastCompressed(const CompressedNeighbors &cnl, const VidList &right, size_t depth) {
    if (config_.emit_stdout || checksum_out_.is_open()) {
      Report(cnl, right);
      return;
    }
    V42HashState left;
    const auto &root_nbrs = bi_graph_.VertexV(result_tree_root_vid_)->neighbors;
    for (const auto &[idx,bits] : cnl) {
      size_t b = bits;
      while (b) {
        left.add(root_nbrs[idx * NumBits + __builtin_ctzl(b)]->label);
        b &= b - 1;
      }
    }
    const auto &lower = v42_lower_hash_stack_[depth];
    const size_t lsize = swap_vertices_ ? lower.size : left.size;
    const size_t rsize = swap_vertices_ ? left.size : lower.size;
    if (lsize < config_.min_left || rsize < config_.min_right) return;
    ++bic_cnt_;
    const uint64_t hu = left.finish();
    const uint64_t hl = lower.finish();
    const uint64_t hleft = swap_vertices_ ? hl : hu;
    const uint64_t hright = swap_vertices_ ? hu : hl;
    const uint64_t h = SplitMix64(SplitMix64(hleft + 0x6a09e667f3bcc909ULL) ^
                                  SplitMix64(hright + 0xbb67ae8584caa73bULL));
    stats_.checksum_xor ^= h;
    stats_.checksum_sum += h;
  }
  std::vector<V42HashState> v42_lower_hash_stack_;
#endif

  void Report(const CompressedNeighbors &CNL, const VidList &R) {
    VidList L;
    auto &nbrs = bi_graph_.VertexV(result_tree_root_vid_)->neighbors;
    for (auto [idx, cpn] : CNL) {
      while (cpn > 0) {
        L.emplace_back(nbrs[idx * NumBits + __builtin_ctzl(cpn)]->vid);
        cpn &= cpn - 1;
      }
    }
    HandleOutput(L, R);
  }

  VidList ComputeUpperForLower(const VidList &lower) const {
    VidList upper;
    if (lower.empty()) return upper;
    const auto &first = bi_graph_.VertexV(lower.front())->neighbors;
    upper.reserve(first.size());
    for (const auto &u : first) upper.emplace_back(u->vid);
    for (size_t k = 1; k < lower.size() && !upper.empty(); ++k) {
      const auto &nbrs = bi_graph_.VertexV(lower[k])->neighbors;
      VidList next;
      next.reserve(std::min(upper.size(), nbrs.size()));
      size_t i = 0, j = 0;
      while (i < upper.size() && j < nbrs.size()) {
        auto a = upper[i], b = nbrs[j]->vid;
        if (a == b) { next.emplace_back(a); ++i; ++j; }
        else if (a < b) ++i;
        else ++j;
      }
      upper.swap(next);
    }
    return upper;
  }

  void EnumeratePlain(ResultTreeNode *node, vid_t vid, const VidList &parent_upper, VidList &R) {
    result_tree_size_++;
    R.emplace_back(vid);
    VidList current_upper;
    const auto &nbr_ptrs = bi_graph_.VertexV(vid)->neighbors;
    if (parent_upper.empty()) {
      current_upper.reserve(nbr_ptrs.size());
      for (const auto &u : nbr_ptrs) current_upper.emplace_back(u->vid);
    } else {
      current_upper.reserve(std::min(parent_upper.size(), nbr_ptrs.size()));
      size_t i = 0, j = 0;
      while (i < parent_upper.size() && j < nbr_ptrs.size()) {
        auto a = parent_upper[i], b = nbr_ptrs[j]->vid;
        if (a == b) { current_upper.emplace_back(a); ++i; ++j; }
        else if (a < b) ++i;
        else ++j;
      }
    }
    if (node->is_end) HandleOutput(current_upper, R);
    for (auto rit = node->children.rbegin(); rit != node->children.rend(); ++rit) {
      EnumeratePlain(rit->second.get(), rit->first, current_upper, R);
    }
    R.pop_back();
  }

  // Result-path lookup used both in normal DFS and in matching MIS terminal output.
  // Keeping this centralized makes the hot-child A/B isolate map lookup overhead.
  ResultTreeNode *EnsureResultChild(ResultTreeNode *parent, vid_t child_key) {
#ifdef MBE_ET13_DIAG
    ++et13_.v39_result_ensure_calls;
#endif
#ifdef MBE_V31_RESULT_HOT
    if (parent->hot_child != nullptr && parent->hot_key == child_key) {
      ++v31_result_hot_hits_;
      return parent->hot_child;
    }
#endif
    auto [it, fresh] = parent->children.try_emplace(child_key, nullptr);
    if (fresh) {
      it->second = std::make_unique<ResultTreeNode>();
      ++result_tree_size_cur_;
#ifdef MBE_ET13_DIAG
      ++et13_.v39_result_created_nodes;
#endif
    }
#ifdef MBE_V31_RESULT_HOT
    parent->hot_key = child_key;
    parent->hot_child = it->second.get();
#endif
    return it->second.get();
  }

  bool InsertResultPath(const VidList &path) {
    if (path.empty()) return false;
    ResultTreeNode *r = nullptr;
    for (size_t i = 0; i < path.size(); ++i) {
      vid_t v = path[i];
      if (i == 0) {
        if (!result_tree_roots_[v]) {
          result_tree_roots_[v] = std::make_unique<ResultTreeNode>();
          result_tree_size_cur_++;
        }
        r = result_tree_roots_[v].get();
      } else {
        r = EnsureResultChild(r, v);
      }
    }
    if (r->is_end) {
      duplicated_cnt_++;
      return false;
    }
    r->is_end = true;
    stats_.et_generated_lower_layers++;
    return true;
  }

  void CollectCandidatePaths(NeighborTreeNode *node, VidList &cur, std::vector<VidList> &paths) const {
    cur.emplace_back(node->vid);
    if (node->is_end) paths.emplace_back(cur);
    for (const auto &[id, child] : node->children) CollectCandidatePaths(child.get(), cur, paths);
    cur.pop_back();
  }

#ifdef MBE_ET13_DIAG
  // V51 structure probe: a FULL candidate family (not an ET/TG prefix).
  // The sample is skipped, not classified, if path/column bounds are exceeded.
  // Only candidate-tree paths are inspected: no graph probes or result writes.
  void V51ClassifyTerminalFamily(NeighborTreeNode *root) {
    ++et13_.profile_samples;
    std::vector<VidList> paths;
    VidList cur;
    std::set<vid_t> distinct;
    bool oversized = false;
    auto visit = [&](auto&& self, NeighborTreeNode *n) -> void {
      if (oversized) return;
      if (cur.size() >= config_.v51_max_cols) {oversized=true;return;}
      cur.push_back(n->vid);
      distinct.insert(n->vid);
      if (distinct.size() > config_.v51_max_cols) {oversized=true;cur.pop_back();return;}
      if (n->is_end) {
        if (paths.size() >= config_.v51_max_paths) {oversized=true;cur.pop_back();return;}
        paths.push_back(cur);
      }
      for (auto &[id,c] : n->children) {
        self(self,c.get());
        if (oversized) break;
      }
      cur.pop_back();
    };
    for (auto &[id,c] : root->children) {
      visit(visit,c.get());
      if (oversized) break;
    }
    if (oversized || paths.size()<2 || distinct.empty()) {
      ++et13_.profile_sample_oversize;
      return;
    }
    ++et13_.profile_sample_bounded;
    et13_.profile_candidate_paths += paths.size();
    VidList universe(distinct.begin(),distinct.end());
    std::map<vid_t, unsigned> misses;
    bool two_misses_per_row=true;
    for (const auto &p:paths) {
      size_t i=0, j=0, row_misses=0;
      while(i<universe.size()) {
        if(j<p.size() && p[j]==universe[i]) {++i;++j;}
        else {++misses[universe[i++]]; ++row_misses;}
      }
      if (row_misses>2) {two_misses_per_row=false;break;}
    }
    if (!two_misses_per_row) {++et13_.profile_other;return;}
    size_t shared=0;
    for (const auto &[col,n]:misses) if(n>1) ++shared;
    if (shared==0) ++et13_.profile_matching;
    else if (shared==1) {
      ++et13_.profile_one_exception;
      ++et13_.profile_exception_columns;
      auto count=paths.size();
      unsigned bucket=count<4?0:count<8?1:count<16?2:count<32?3:4;
      ++et13_.profile_one_exception_family[bucket];
    } else ++et13_.profile_other;
  }
#endif

  size_t CountEndPathsUpTo(NeighborTreeNode *node, size_t cap) const {
    size_t cnt = node->is_end ? 1 : 0;
    if (cnt >= cap) return cnt;
    for (const auto &[id, child] : node->children) {
      cnt += CountEndPathsUpTo(child.get(), cap - cnt);
      if (cnt >= cap) break;
    }
    return cnt;
  }

  // A 1-biplex whose complement has maximum degree one is a matching.
  // Each complement edge (row_i, missing_column_i) forces a maximal
  // independent set to choose exactly one endpoint. Every isolated vertex
  // is mandatory. Rows are implicit in one-sided MBET's candidate tree;
  // selecting a row endpoint corresponds to omitting its missing column.
  //
  // Unlike the 2026 IPS counting shortcut, we must explicitly ENUMERATE
  // maximal independent sets and insert the corresponding lower-side paths
  // into MBET's result trie. Reusing trie prefixes avoids constructing a
  // fresh lower-side vector and re-traversing its entire prefix per output.
  ResultTreeNode *AppendMISColumn(ResultTreeNode *prefix, vid_t v) {
#ifdef MBE_V29_PROFILE
    auto v29_append_watch = DebugTimer<44>::AutoWatch();
#endif
    if (!prefix) {
      auto &root = result_tree_roots_[v];
      if (!root) {
        root = std::make_unique<ResultTreeNode>();
        ++result_tree_size_cur_;
      }
      return root.get();
    }
    return EnsureResultChild(prefix, v);
  }

  bool ResolveMatchingTerminal(const std::vector<vid_t> &universe,
                               std::vector<vid_t> defects,
                               bool has_full_row) {
#ifdef MBE_V29_PROFILE
    auto v29_mis_watch = DebugTimer<43>::AutoWatch();
#endif
#ifdef MBE_ET13_DIAG
    ET13TimedRegion et13_resolve_timer(et13_.resolve_wall_ns);
    const uint64_t before_new = stats_.et_generated_lower_layers;
    const uint64_t before_dups = duplicated_cnt_;
#endif
    std::sort(defects.begin(), defects.end());
    defects.erase(std::unique(defects.begin(), defects.end()), defects.end());
    ++stats_.et_hits;
#ifdef MBE_ET13_DIAG
    ++et13_.successful;
    et13_.matched_edges_total += defects.size();
    size_t bucket = defects.size()<4 ? defects.size() : (defects.size()<8 ? 4 : 5);
    ++et13_.matching_size_buckets[bucket];
#endif

    // The verifier already owns a sorted, movable defect vector. Convert
    // its entries in place to column indices, avoiding another allocation
    // for every successful terminal.
    size_t ui = 0;
    for (auto &d : defects) {
      while (ui < universe.size() && universe[ui] < d) ++ui;
      if (ui == universe.size() || universe[ui] != d)
        throw std::logic_error("ET matching defect missing from universe");
      d = ui;
    }

    auto append_mandatory = [&](ResultTreeNode *prefix, size_t begin,
                                size_t end) -> ResultTreeNode * {
      for (size_t i = begin; i < end; ++i)
        prefix = AppendMISColumn(prefix, universe[i]);
      return prefix;
    };

    // 'chose_row' means at least one matching edge chose its row endpoint
    // (thus omitted that edge's column). If there are no full rows, an
    // all-column independent set has no row on the other side and is not
    // a biclique under the original one-sided terminal semantics.
    auto enumerate_mis = [&](auto &&self, size_t edge_index,
                             size_t next_column, ResultTreeNode *prefix,
                             bool chose_row) -> void {
      if (edge_index == defects.size()) {
        if (!has_full_row && !chose_row) return;
        prefix = append_mandatory(prefix, next_column, universe.size());
        if (!prefix) return; // Empty lower side is not an output.
        if (prefix->is_end) {
          ++duplicated_cnt_;
        } else {
          prefix->is_end = true;
          ++stats_.et_generated_lower_layers;
        }
        return;
      }

      const size_t column = defects[edge_index];
      prefix = append_mandatory(prefix, next_column, column);

      // Choice 1: keep this column, exclude the row endpoint.
      // Skip the all-column (zero-row) leaf before creating any trie node.
      if (has_full_row || chose_row || edge_index + 1 < defects.size()) {
        auto *with_column = AppendMISColumn(prefix, universe[column]);
        self(self, edge_index + 1, column + 1, with_column, chose_row);
      }
      // Choice 2: keep the row endpoint, omit its missing column.
      self(self, edge_index + 1, column + 1, prefix, true);
    };
    enumerate_mis(enumerate_mis, 0, 0, nullptr, false);
#ifdef MBE_ET13_DIAG
    et13_.new_result_paths += stats_.et_generated_lower_layers - before_new;
    et13_.duplicate_result_paths += duplicated_cnt_ - before_dups;
#endif
    return true;
  }

  struct TGPrefixPlan {
    bool active = false;
    bool two_biplex = false;
    std::vector<VidList> two_biplex_outputs;
    size_t prefix_paths = 0;
    std::vector<vid_t> universe;
    std::vector<vid_t> defects;
    bool has_full_row = false;
    size_t last_deferred_preorder = 0;
  };

  // Stored only for the current Find call. The canonical DFS metadata is not
  // generated until after ET, so terminal pointers are marked later in Find().
  // An ET stream may inspect beyond TG's fixed prefix cap; when it reaches that
  // cap it takes exactly one snapshot of the compatible prefix state.
  struct SharedTGHint {
    TGPrefixPlan plan;
    NeighborTreeNode *ends[64];
    size_t accepted = 0;
  };

  void CollectFirstCandidateEnds(NeighborTreeNode *node,
                                 VidList &cur,
                                 std::vector<VidList> &paths,
                                 std::vector<NeighborTreeNode *> &ends,
                                 size_t cap) const {
    if (paths.size() >= cap) return;
    cur.emplace_back(node->vid);
    if (node->is_end) {
      paths.emplace_back(cur);
      ends.emplace_back(node);
    }
    if (paths.size() < cap) {
      for (const auto &[id, child] : node->children) {
        CollectFirstCandidateEnds(child.get(), cur, paths, ends, cap);
        if (paths.size() >= cap) break;
      }
    }
    cur.pop_back();
  }

  // V54 scratch is only used inside one non-reentrant ET2 call. A successful
  // terminal does not recursively call Find. Other Find calls are sequential,
  // so retained vectors cannot alias a live nested terminal execution.
  struct ET2Scratch {
    VidList cur;
    std::vector<VidList> first_three;
    std::vector<NeighborTreeNode*> ignored;
    VidList universe;
    std::vector<uint8_t> col_degree;
    std::vector<std::pair<size_t, size_t>> defects;
    std::vector<size_t> active_rows, active_cols;
    std::vector<uint64_t> closed, mis;
    std::vector<ResultTreeNode*> cached_prefix;
  };

  // V53: Full-family 2-biplex terminal. The complement H has an edge
  // (candidate row, union column) precisely where that row omits that column.
  // H has maximum degree <= 2 iff every row misses <= 2 columns and each
  // column is missed by <= 2 rows. Therefore H consists of paths, even
  // cycles and isolated vertices. We enumerate its maximal independent sets.
  // A maximal independent set selecting at least one row and column uniquely
  // defines a nonempty maximal intersection of the input candidate family.
  // Empty-side MISes are excluded. We must finish enumeration AND respect the
  // output cap *before* touching the global result trie; otherwise DFS fallback
  // would observe half-committed intermediate ownership state.
  bool TryTwoBiplexTerminal(NeighborTreeNode *root) {
    if (!config_.et || !config_.et_root_enabled) return false;
    ++stats_.et2_attempts;
    if (root->is_end) {
      // The original ET ignores the dummy-root empty terminal path.
      // Be conservative: fallback instead of changing established semantics.
      ++stats_.et2_fallback_shape;
      return false;
    }
    const size_t paths_count = root->end_count;
    if (paths_count < config_.et_min_paths) return false;
    // V54: the first root-child's vertex appears in at least one terminal row,
    // and cannot occur in any row of a *later* root child (sorted trie order).
    // Every such later row therefore contributes one complement edge incident
    // to that vertex. If their terminal counts sum to >2, max-degree <=2 is
    // impossible. Skip ONLY the ET attempt; original DFS remains untouched.
    // This does not rely on an assumed root.end_count == sum of children.
    if (config_.et2_root_degree_gate && root->children.size() > 1) {
      auto it = root->children.begin(); ++it;
      size_t later_rows = 0;
      for (; it != root->children.end(); ++it) {
        if (it->second->end_count > 2 - later_rows) {
          ++stats_.et2_root_gate_rejections;
          return false;
        }
        later_rows += it->second->end_count;
      }
    }
    if (root->min_end_len < 2 || root->max_end_len < 2) return false;
    const size_t min_len = root->min_end_len - 1;
    const size_t max_len = root->max_end_len - 1;
    // Any row may miss at most two elements of the union.
    if (max_len > min_len + 2 || paths_count > 2 * (max_len + 2) + 1) {
      ++stats_.et2_fallback_shape;
      return false;
    }

    ET2Scratch local_scratch;
    ET2Scratch &scratch = config_.et2_reuse_buffers ? et2_scratch_ : local_scratch;
    if (config_.et2_reuse_buffers) ++stats_.et2_scratch_reused_calls;
    auto &cur = scratch.cur;
    auto &first_three = scratch.first_three;
    auto &ignored = scratch.ignored;
    cur.clear(); first_three.clear(); ignored.clear();
    for (const auto &[id, child] : root->children) {
      CollectFirstCandidateEnds(child.get(), cur, first_three, ignored, 3);
      if (first_three.size() == 3) break;
    }
    if (first_three.size() < 2) return false;
    auto &universe = scratch.universe;
    universe.assign(first_three[0].begin(), first_three[0].end());
    for (size_t i = 1; i < first_three.size(); ++i) {
      VidList merged;
      merged.reserve(universe.size() + first_three[i].size());
      std::set_union(universe.begin(), universe.end(),
                     first_three[i].begin(), first_three[i].end(),
                     std::back_inserter(merged));
      universe.swap(merged);
    }
    if (universe.empty() || universe.size() > max_len + 2) {
      ++stats_.et2_fallback_shape;
      return false;
    }
    ++stats_.et2_verified;
    auto &col_degree = scratch.col_degree;
    col_degree.assign(universe.size(), 0);
    auto &defects = scratch.defects;
    defects.clear();
    defects.reserve(std::min(config_.et2_max_defects + 1, paths_count * size_t(2)));
    size_t seen = 0;
    bool has_full_row = false;
    bool degree_bad = false, cap_bad = false;
    auto inspect = [&](const VidList &path) -> bool {
      const size_t row_id = seen++;
      size_t ui=0, pi=0, missing=0;
      while (ui < universe.size()) {
        if (pi < path.size() && path[pi] == universe[ui]) {
          ++ui; ++pi;
          continue;
        }
        if (pi < path.size() && path[pi] < universe[ui]) {
          degree_bad=true; return false; // union of first 3 MUST cover
        }
        if (++missing > 2 || ++col_degree[ui] > 2) {
          degree_bad=true; return false;
        }
        defects.emplace_back(row_id, ui);
        if (defects.size() > config_.et2_max_defects) {
          cap_bad=true; return false;
        }
        ++ui;
      }
      if (pi != path.size()) {degree_bad=true;return false;}
      if (!missing) has_full_row=true;
      return true;
    };
    auto walk = [&](auto&& self, const NeighborTreeNode *n)->bool {
      cur.push_back(n->vid);
      bool valid = !n->is_end || inspect(cur);
      if (valid) for (const auto &[id, ch] : n->children) {
        if (!self(self, ch.get())) {valid=false;break;}
      }
      cur.pop_back();
      return valid;
    };
    bool valid = true;
    for (const auto &[id, child] : root->children) {
      if (!walk(walk, child.get())) {valid=false;break;}
    }
    if (!valid || seen != paths_count) {
      if (cap_bad) ++stats_.et2_fallback_cap;
      else ++stats_.et2_fallback_degree;
      return false;
    }

    // Compress away isolated vertices. Isolated rows must be selected in
    // every MIS; isolated columns are always part of every result column set.
    auto &active_rows = scratch.active_rows;
    auto &active_cols = scratch.active_cols;
    active_rows.clear(); active_cols.clear();
    active_rows.reserve(defects.size());
    active_cols.reserve(defects.size());
    for (const auto &[r,c] : defects) {
      active_rows.push_back(r); active_cols.push_back(c);
    }
    std::sort(active_rows.begin(), active_rows.end());
    active_rows.erase(std::unique(active_rows.begin(), active_rows.end()), active_rows.end());
    std::sort(active_cols.begin(), active_cols.end());
    active_cols.erase(std::unique(active_cols.begin(), active_cols.end()), active_cols.end());
    const size_t nr=active_rows.size(), nc=active_cols.size(), nv=nr+nc;
    if (nv > 60) {++stats_.et2_fallback_cap;return false;}
    auto &closed = scratch.closed;
    closed.assign(nv, 0);
    for (size_t i=0;i<nv;++i) closed[i]=uint64_t(1)<<i;
    for (const auto &[r,c] : defects) {
      const size_t ri = std::lower_bound(active_rows.begin(),active_rows.end(),r)-active_rows.begin();
      const size_t ci = nr + (std::lower_bound(active_cols.begin(),active_cols.end(),c)-active_cols.begin());
      closed[ri] |= uint64_t(1)<<ci;
      closed[ci] |= uint64_t(1)<<ri;
    }
    const uint64_t all=(nv ? ((uint64_t(1)<<nv)-1) : 0);
    const uint64_t row_mask=(nr ? ((uint64_t(1)<<nr)-1) : 0);
    const uint64_t col_mask=all & ~row_mask;
    auto &mis = scratch.mis;
    mis.clear();
    mis.reserve(std::min(size_t(64),config_.et2_max_mis));
    bool overflow=false;

    // Disjoint branching on a currently undominated vertex v: a maximal
    // independent set must choose at least one member of N[v]. Branches
    // choose the earliest such selected member, forbidding earlier options.
    // This yields each MIS exactly once even for paths and even cycles.
    auto enumerate=[&](auto&& self, uint64_t selected, uint64_t dominated,
                       uint64_t forbidden)->void {
      if (overflow) return;
      if (dominated==all) {
        // Some non-defect rows may be isolated; they are mandatory.
        const bool row_present = has_full_row || (selected & row_mask);
        const bool column_present = universe.size()>nc || (selected & col_mask);
        if (row_present && column_present) {
          if (mis.size()==config_.et2_max_mis) {overflow=true;return;}
          mis.push_back(selected);
        }
        return;
      }
      uint64_t undominated=all & ~dominated;
      // Early detect any vertex that can no longer be dominated.
      const uint64_t allowed=all & ~forbidden;
      for (uint64_t tmp=undominated;tmp;tmp &= tmp-1) {
        const unsigned v=__builtin_ctzll(tmp);
        if (!(closed[v] & allowed)) return;
      }
      const unsigned v=__builtin_ctzll(undominated);
      uint64_t options=closed[v] & allowed;
      uint64_t earlier=0;
      while (options && !overflow) {
        const uint64_t choice=options & (~options+1);
        const unsigned w=__builtin_ctzll(choice);
        self(self, selected | choice, dominated | closed[w],
             forbidden | earlier | (closed[w] & ~choice));
        earlier |= choice;
        options &= options-1;
      }
    };
    enumerate(enumerate, 0, 0, 0);
    if (overflow) {++stats_.et2_fallback_cap;return false;}

    ++stats_.et_hits;
    ++stats_.et2_hits;
    bool nonmatching=false;
    for (size_t i=0;i<nv;++i)
      if (__builtin_popcountll(closed[i]) > 2) {nonmatching=true;break;}
    if (nonmatching) ++stats_.et2_nonmatching_hits;
    stats_.et2_mis_generated += mis.size();
    // V54: the global Result Tree is the canonical owner/dedup authority.
    // Only local output order is changed; each same MIS path is inserted once.
    // Sort by decisions on increasing active columns, with kept columns first,
    // to increase prefix locality (no mutation until all MIS are enumerated).
    const bool reuse = config_.et2_trie_prefix_reuse &&
                       mis.size() >= config_.et2_reuse_min_mis && nc > 0;
    auto &cached_prefix = scratch.cached_prefix;
    uint64_t prev_col_bits = 0;
    if (reuse) {
      const uint64_t mask = (uint64_t(1) << nc) - 1;
      std::sort(mis.begin(), mis.end(), [&](uint64_t lhs, uint64_t rhs) {
        const uint64_t a = (lhs >> nr) & mask;
        const uint64_t b = (rhs >> nr) & mask;
        const uint64_t diff = a ^ b;
        if (!diff) return false;
        const unsigned first = __builtin_ctzll(diff);
        return ((a >> first) & 1) > ((b >> first) & 1);
      });
      cached_prefix.resize(universe.size(), nullptr);
      ++stats_.et2_trie_reuse_batches;
    }
    bool have_previous = false;
    for (uint64_t selected : mis) {
      ResultTreeNode *prefix = nullptr;
      size_t begin = 0;
      const uint64_t col_bits = selected >> nr;
      if (reuse && have_previous) {
        const uint64_t delta = prev_col_bits ^ col_bits;
        if (!delta) throw std::logic_error("V54 repeated ET2 column projection");
        const size_t first_changed_col = active_cols[__builtin_ctzll(delta)];
        // Prior and current result paths have identical kept/omitted columns
        // until 'first_changed_col'. cached_prefix[i] is the trie node after
        // processing universe[0..i], including any skipped columns.
        begin = first_changed_col;
        if (begin) prefix = cached_prefix[begin-1];
        stats_.et2_trie_reused_columns += begin;
      }
      size_t ci=std::lower_bound(active_cols.begin(), active_cols.end(), begin)-active_cols.begin();
      for (size_t i=begin;i<universe.size();++i) {
        bool keep=true;
        if (ci<active_cols.size() && active_cols[ci]==i) {
          keep=bool(col_bits & (uint64_t(1) << ci));
          ++ci;
        }
        if (keep) prefix=AppendMISColumn(prefix,universe[i]);
        if (reuse) cached_prefix[i] = prefix;
      }
      if (!prefix) throw std::logic_error("V54 internal empty column set");
      if (prefix->is_end) ++duplicated_cnt_;
      else {prefix->is_end=true; ++stats_.et_generated_lower_layers;}
      prev_col_bits = col_bits;
      have_previous = true;
    }
    return true;
  }

#ifdef MBE_V58_COST_PROFILE
  struct V58ScopedTimer {
    uint64_t &total;
    std::chrono::steady_clock::time_point start;
    explicit V58ScopedTimer(uint64_t &dst) : total(dst),start(std::chrono::steady_clock::now()) {}
    ~V58ScopedTimer() { total += static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                                      std::chrono::steady_clock::now()-start).count()); }
  };
  static uint64_t V58Elapsed(std::chrono::steady_clock::time_point p) {
    return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                                     std::chrono::steady_clock::now()-p).count());
  }
#endif

  // V56: three alternate, fully transactional terminal solvers.
  // All operate on the exact terminal path family of the current candidate
  // tree; no result trie mutation is made until the full bounded answer is
  // known. The ordinary MBET Find recursion is the complete fallback.
  bool TryV56Terminal(NeighborTreeNode *root) {
    if (!config_.et || !config_.v56_terminal || !config_.et_root_enabled || root->is_end)
      return false;
#ifdef MBE_V58_COST_PROFILE
    V58ScopedTimer v58_total_timer(stats_.v58_total_ns);
    const auto v58_shape_start=std::chrono::steady_clock::now();
#endif
    ++stats_.v56_attempts;
    const size_t n=root->end_count;
    // Necessary *admission* conditions only: rejecting never prunes MBET DFS.
    // Avoid overflow in the product check, while remaining O(1) in the search.
    if(config_.v56_terminal==3 && config_.v58_min_path_work &&
       (!root->max_end_len || n<((config_.v58_min_path_work-1)/root->max_end_len+1))) {
      ++stats_.v58_gate_work_reject;
      return false;
    }
    if(config_.v56_terminal==3 && config_.v58_max_length_spread &&
       root->max_end_len>=root->min_end_len &&
       root->max_end_len-root->min_end_len>config_.v58_max_length_spread) {
      ++stats_.v58_gate_spread_reject;
      return false;
    }
    if (n<config_.v56_min_paths || n>config_.v56_max_paths) return false;
    if (!root->min_end_len || !root->max_end_len ||
        root->min_end_len==std::numeric_limits<size_t>::max() ||
        root->max_end_len>config_.v56_max_cols+1) return false;
    const bool lazy_mask = config_.v56_terminal==3 && config_.v60_lazy_mask;
    // Every root-child key smaller than the greatest first-column key must be
    // absent from at least one terminal path; all such keys belong to D.
    // Also |D| >= max(path_length)-min(path_length). These are safe necessary
    // conditions; rejection NEVER drops a biclique, it chooses normal DFS.
    if(config_.v56_terminal==3 && config_.v60_root_gate) {
      if(root->children.size()>config_.v56_max_bits+1 ||
         root->max_end_len-root->min_end_len>config_.v56_max_bits) {
        ++stats_.v60_root_reject;
        return false;
      }
    }
    std::vector<VidList> paths;
    VidList universe;
    VidList prepared_core;
    // A flat, reusable row buffer is optional. It allows the mask closure to
    // consume precisely the same path family without walking the tree twice.
    // Failed probes do not modify result ownership or the candidate tree.
    auto &v61_flat_rows = v61_flat_rows_scratch_;
    auto &v61_flat_offsets = v61_flat_offsets_scratch_;
    const bool flat_rows = lazy_mask && config_.v61_flat_rows;
    if(flat_rows) {v61_flat_rows.clear();v61_flat_offsets.clear();}
    if(lazy_mask) {
      // Both union and intersection evolve monotonically as paths arrive.
      // Thus |union|-|intersection| never decreases; abort once it exceeds
      // the exact bitmask cap, avoiding path materialization on failure.
      VidList walk, tmp_union, tmp_core;
      size_t path_count=0;
      bool rejected=false;
      auto stream_probe=[&](auto&& self,const NeighborTreeNode *x)->void {
        if(rejected)return;
        walk.push_back(x->vid);
        if(x->is_end) {
          ++path_count;
          ++stats_.v60_probe_paths;
          if(flat_rows) {
            v61_flat_rows.insert(v61_flat_rows.end(),walk.begin(),walk.end());
            v61_flat_offsets.push_back(v61_flat_rows.size());
            ++stats_.v61_flat_rows_captured;
          }
          if(path_count==1) {
            universe=walk;
            prepared_core=walk;
          } else {
            tmp_union.clear();
            std::set_union(universe.begin(),universe.end(),walk.begin(),walk.end(),
                           std::back_inserter(tmp_union));
            universe.swap(tmp_union);
            if(universe.size()>config_.v56_max_cols) rejected=true;
            if(!rejected) {
              tmp_core.clear();
              std::set_intersection(prepared_core.begin(),prepared_core.end(),
                                    walk.begin(),walk.end(),std::back_inserter(tmp_core));
              prepared_core.swap(tmp_core);
              if(universe.size()-prepared_core.size()>config_.v56_max_bits)
                rejected=true;
            }
          }
          if(universe.size()>config_.v56_max_cols) rejected=true;
        }
        if(!rejected)for(const auto &[id,ch]:x->children)self(self,ch.get());
        walk.pop_back();
      };
      for(const auto &[id,ch]:root->children) {
        stream_probe(stream_probe,ch.get());
        if(rejected)break;
      }
      if(rejected) {++stats_.v60_early_reject;return false;}
      if(path_count!=n) throw std::logic_error("V60 lazy terminal count drift");
      ++stats_.v60_probe_success;
    } else {
      paths.reserve(n);
      VidList row;
      auto collect=[&](auto&& self,const NeighborTreeNode *x)->void {
        row.push_back(x->vid);
        if (x->is_end) paths.emplace_back(row);
        for(const auto &[id,ch]:x->children)self(self,ch.get());
        row.pop_back();
      };
      for(const auto &[id,ch]:root->children)collect(collect,ch.get());
      if(paths.size()!=n)throw std::logic_error("V56 terminal count drift");
      universe=paths.front();
      for(size_t i=1;i<paths.size();++i) {
        VidList tmp;
        tmp.reserve(universe.size()+paths[i].size());
        std::set_union(universe.begin(),universe.end(),paths[i].begin(),paths[i].end(),
                       std::back_inserter(tmp));
        universe.swap(tmp);
        if(universe.size()>config_.v56_max_cols) return false;
      }
    }
    if (universe.empty()) return false;
    ++stats_.v56_shape_checked;
#ifdef MBE_V58_COST_PROFILE
    stats_.v58_shape_ns+=V58Elapsed(v58_shape_start);
#endif
    std::vector<VidList> outputs;
    const size_t maxout=config_.et2_max_mis;
    bool overflow=false;
    const size_t method=config_.v56_terminal;
    if(method==3) { // B: enumerate the distinct AND-closure of the row masks.
#ifdef MBE_V58_COST_PROFILE
      const auto v58_prep_start=std::chrono::steady_clock::now();
      ++stats_.v58_mask_prep_calls;
#endif
      VidList core;
      if(lazy_mask)core=std::move(prepared_core);
      else {
        core=paths.front();
        for(size_t i=1;i<paths.size();++i) {
          VidList tmp;
          std::set_intersection(core.begin(),core.end(),paths[i].begin(),paths[i].end(),
                                std::back_inserter(tmp));
          core.swap(tmp);
        }
      }
      VidList changing;
      std::set_difference(universe.begin(),universe.end(),core.begin(),core.end(),
                          std::back_inserter(changing));
      if(changing.empty() || changing.size()>config_.v56_max_bits || changing.size()>20)
        return false;
      // Optional heuristic, never correctness pruning. All fallbacks are DFS.
      if(config_.v60_mask_risk_factor &&
         (size_t(1)<<changing.size()) > n*config_.v60_mask_risk_factor) {
        ++stats_.v60_risk_reject;
        return false;
      }
#ifdef MBE_V58_COST_PROFILE
      stats_.v58_maskprep_ns+=V58Elapsed(v58_prep_start);
      const auto v58_closure_start=std::chrono::steady_clock::now();
      ++stats_.v58_closure_calls;
#endif
      const size_t states=size_t(1)<<changing.size();
      std::vector<uint8_t> local_seen;
      std::vector<uint32_t> local_closed;
      if(!config_.v57_mask_fast_closure)local_seen.assign(states,0);
      else {
        if(v57_seen_epochs_.size()<states)v57_seen_epochs_.resize(states,0);
        if(++v57_epoch_==0) {std::fill(v57_seen_epochs_.begin(),v57_seen_epochs_.end(),0);v57_epoch_=1;}
      }
      auto &closed_masks=config_.v57_mask_fast_closure?v57_closure_scratch_:local_closed;
      closed_masks.clear();
      if(closed_masks.capacity()<std::min(maxout+1,states))
        closed_masks.reserve(std::min(maxout+1,states));
      auto register_mask=[&](uint32_t m) {
        if(config_.v57_mask_fast_closure) {
          if(v57_seen_epochs_[m]==v57_epoch_)return;
          v57_seen_epochs_[m]=v57_epoch_;
        } else {
          if(local_seen[m])return;
          local_seen[m]=1;
        }
        closed_masks.push_back(m);
        if(closed_masks.size()>maxout)overflow=true;
      };
      // Rows are sorted increasing vid_t; lazy mode computes each row mask
      // directly from the Candidate Tree without creating vector<VidList>.
      // V62: separate the closure algebra from column-to-mask encoding, so the
      // latter may be shared by all terminal rows passing through a trie node.
      // No mutation of the candidate tree or Result Tree occurs before closure
      // cap/risk checks, preserving the exact fallback contract.
      auto consume_bits=[&](uint32_t bits) {
        const size_t previous=closed_masks.size();
        register_mask(bits);
        for(size_t i=0;i<previous && !overflow;++i)register_mask(closed_masks[i]&bits);
      };
      auto consume_path=[&](const VidList &p) {
        ++stats_.v60_lazy_masks;
        size_t j=0;
        uint32_t bits=0;
        for(size_t k=0;k<changing.size();++k) {
          while(j<p.size() && p[j]<changing[k]) ++j;
          if(j<p.size() && p[j]==changing[k])bits|=uint32_t(1)<<k;
        }
        consume_bits(bits);
      };
      if(lazy_mask && flat_rows) {
        size_t beg=0;
        for(size_t end:v61_flat_offsets) {
          if(overflow)break;
          // Compact rows are stored without a per-row heap allocation.
          // Reuse a small vector view for the same canonical column IDs.
          v61_row_scratch_.assign(v61_flat_rows.begin()+beg,v61_flat_rows.begin()+end);
          consume_path(v61_row_scratch_);
          beg=end;
        }
      } else if(lazy_mask && config_.v62_tree_mask) {
        // The paths in the candidate trie share prefixes. A node contributes
        // its changing-column bit to EVERY descendant terminal row, so carry
        // that bit in the DFS state instead of rescanning its full path for
        // each emitted row. Lookup uses the sorted <=20 changing columns.
        auto stream_masks=[&](auto&& self,const NeighborTreeNode *x,
                              uint32_t bits,size_t next)->void {
          if(overflow)return;
          ++stats_.v62_tree_mask_nodes;
          if(config_.v62_mask_cursor) {
            // All root-to-leaf candidate paths strictly increase in column ID.
            // Carry the next possibly matching changing column into children.
            while(next<changing.size() && changing[next]<x->vid) ++next;
            if(next<changing.size() && changing[next]==x->vid) {
              bits |= uint32_t(1) << static_cast<unsigned>(next);
              ++next;
            }
          } else {
            const auto it=std::lower_bound(changing.begin(),changing.end(),x->vid);
            if(it!=changing.end() && *it==x->vid)
              bits |= uint32_t(1) << static_cast<unsigned>(it-changing.begin());
          }
          if(x->is_end) {
            ++stats_.v60_lazy_masks;
            ++stats_.v62_tree_mask_leaves;
            consume_bits(bits);
          }
          if(!overflow)for(const auto &[id,ch]:x->children)
            self(self,ch.get(),bits,next);
        };
        for(const auto &[id,ch]:root->children) {
          stream_masks(stream_masks,ch.get(),0,0);
          if(overflow)break;
        }
      } else if(lazy_mask) {
        VidList row;
        auto stream_masks=[&](auto&& self,const NeighborTreeNode *x)->void {
          if(overflow)return;
          row.push_back(x->vid);
          if(x->is_end)consume_path(row);
          if(!overflow)for(const auto &[id,ch]:x->children)self(self,ch.get());
          row.pop_back();
        };
        for(const auto &[id,ch]:root->children) {
          stream_masks(stream_masks,ch.get());
          if(overflow)break;
        }
      } else {
        for(const auto &p:paths) {
          // Legacy branch retains its own work counters and execution order.
          size_t j=0;
          uint32_t bits=0;
          for(size_t k=0;k<changing.size();++k) {
            while(j<p.size() && p[j]<changing[k]) ++j;
            if(j<p.size() && p[j]==changing[k])bits|=uint32_t(1)<<k;
          }
          const size_t old=closed_masks.size();
          register_mask(bits);
          for(size_t i=0;i<old && !overflow;++i)register_mask(closed_masks[i]&bits);
          if(overflow)break;
        }
      }
      if(overflow) {++stats_.v56_cap_reject;return false;}
      ++stats_.v57_mask_closed;
      stats_.v57_mask_candidates+=closed_masks.size();
      // Adaptive output-aware policy: a closure with many distinct masks may
      // be more expensive to materialize than the ordinary candidate DFS.
      // This decision is made *before* any Result Tree mutation.
      if(config_.v57_mask_output_factor &&
         closed_masks.size()>n*config_.v57_mask_output_factor) {
        ++stats_.v57_mask_output_reject;
        return false;
      }
#ifdef MBE_V58_COST_PROFILE
      stats_.v58_closure_ns+=V58Elapsed(v58_closure_start);
      const auto v58_emit_start=std::chrono::steady_clock::now();
      ++stats_.v58_emit_calls;
#endif
      if(config_.v57_mask_direct) {
        // No intermediate vector<VidList>. Every mask is a distinct local
        // intersection. Global Result Tree still owns all deduplication.
        // Bit reversal is involutive. Transform each mask exactly once,
        // sort native integers, then undo during emission. The old comparator
        // recomputed two full bit reversals for every sort comparison.
        auto rev32=[](uint32_t x)->uint32_t {
          x=((x&0x55555555u)<<1)|((x>>1)&0x55555555u);
          x=((x&0x33333333u)<<2)|((x>>2)&0x33333333u);
          x=((x&0x0f0f0f0fu)<<4)|((x>>4)&0x0f0f0f0fu);
          x=((x&0x00ff00ffu)<<8)|((x>>8)&0x00ff00ffu);
          return (x<<16)|(x>>16);
        };
        if(config_.v57_mask_prefix) {
          if(config_.v61_fast_sort) {
            for(auto &m:closed_masks)m=rev32(m);
            std::sort(closed_masks.begin(),closed_masks.end());
            ++stats_.v61_fast_sort_batches;
          } else {
            std::sort(closed_masks.begin(),closed_masks.end(),
              [&](uint32_t a,uint32_t b){return rev32(a)<rev32(b);});
          }
        }
        // Build one small bit-index table per terminal state, not per output.
        // The non-changing (mandatory) columns have a zero entry.
        // This routine is nonrecursive until terminal output has completed;
        // reuse the column-flag capacity across all successes, avoiding two
        // short heap allocations on every call. The bit index is capped at 20.
        auto &col_bits=v61_col_bits_scratch_;
        std::array<size_t,20> changing_pos{};
        if(config_.v61_fast_emit) {
          ++stats_.v61_fast_emit_batches;
          col_bits.assign(universe.size(),0);
          size_t at=0;
          for(size_t k=0;k<changing.size();++k) {
            while(at<universe.size() && universe[at]!=changing[k])++at;
            if(at==universe.size())throw std::logic_error("V61 changing position invalid");
            col_bits[at]=uint32_t(1)<<k;
            changing_pos[k]=at;
          }
        }
        // The scratch buffers are local to this nonrecursive emission;
        // reusing their capacity across terminal states avoids allocations.
        auto &prefix=v57_mask_prefix_nodes_;
        if(config_.v57_mask_prefix)prefix.resize(universe.size(),nullptr);
        uint32_t prev_bits=0;
        bool has_prev=false;
        size_t nonempty_emits=0;
        for(uint32_t raw_bits:closed_masks) {
          uint32_t bits=(config_.v61_fast_sort && config_.v57_mask_prefix)?rev32(raw_bits):raw_bits;
          size_t start=0;
          ResultTreeNode *node=nullptr;
          if(config_.v57_mask_prefix && has_prev) {
            const uint32_t delta=bits^prev_bits;
            if(delta==0)throw std::logic_error("V57 duplicate closure mask");
            const size_t first=static_cast<size_t>(__builtin_ctz(delta));
            // Exactly equal kept/omitted sequence before this changing col.
            // Use lower_bound just once, for the first changed column.
            start=config_.v61_fast_emit ? changing_pos[first] :
              size_t(std::lower_bound(universe.begin(),universe.end(),changing[first])-universe.begin());
            if(start)node=prefix[start-1];
            stats_.v57_mask_reused_columns+=start;
          }
          if(config_.v61_fast_emit) {
            for(size_t ui=start;ui<universe.size();++ui) {
              const uint32_t c=col_bits[ui];
              if(!c || (bits&c))node=AppendMISColumn(node,universe[ui]);
              if(config_.v57_mask_prefix)prefix[ui]=node;
            }
          } else {
            size_t di=std::lower_bound(changing.begin(),changing.end(),
                                         universe[start])-changing.begin();
            for(size_t ui=start;ui<universe.size();++ui) {
              bool keep=true;
              if(di<changing.size() && changing[di]==universe[ui]) {
                keep=bool(bits&(uint32_t(1)<<di));
                ++di;
              }
              if(keep)node=AppendMISColumn(node,universe[ui]);
              if(config_.v57_mask_prefix)prefix[ui]=node;
            }
          }
          if(node) {
            if(node->is_end)++duplicated_cnt_;
            else {node->is_end=true;++stats_.et_generated_lower_layers;}
            ++stats_.v57_mask_direct_outputs;
            ++nonempty_emits;
          }
          prev_bits=bits;
          has_prev=true;
        }
        ++stats_.v56_hits;
        ++stats_.et_hits;
        stats_.v56_outputs+=nonempty_emits;
#ifdef MBE_V58_COST_PROFILE
        stats_.v58_emit_ns+=V58Elapsed(v58_emit_start);
#endif
        return true;
      }
      outputs.reserve(closed_masks.size());
      for(uint32_t bits:closed_masks) {
        VidList cols;
        cols.reserve(core.size()+changing.size());
        size_t ci=0,di=0;
        for(vid_t c:universe) {
          if(ci<core.size() && core[ci]==c) {cols.push_back(c);++ci;}
          else {if(bits & (uint32_t(1)<<di))cols.push_back(c);++di;}
        }
        if(!cols.empty())outputs.push_back(std::move(cols));
      }
    } else {
      // A / C: build the sparse bipartite complement and its active graph.
      // Keep only vertices incident to missing edges; all isolated columns
      // and rows are mandatory vertices in every maximal independent set.
      std::vector<std::pair<size_t,size_t>> defects;
      defects.reserve(config_.et2_max_defects+1);
      std::vector<size_t> rdeg(paths.size(),0),cdeg(universe.size(),0);
      for(size_t i=0;i<paths.size();++i) {
        size_t pi=0;
        for(size_t j=0;j<universe.size();++j) {
          while(pi<paths[i].size() && paths[i][pi]<universe[j])++pi;
          if(pi==paths[i].size() || paths[i][pi]!=universe[j]) {
            defects.emplace_back(i,j);++rdeg[i];++cdeg[j];
            if(defects.size()>config_.et2_max_defects)return false;
          }
        }
      }
      std::vector<size_t> active_rows,active_cols;
      for(size_t i=0;i<rdeg.size();++i)if(rdeg[i])active_rows.push_back(i);
      for(size_t i=0;i<cdeg.size();++i)if(cdeg[i])active_cols.push_back(i);
      const size_t nr=active_rows.size(),nc=active_cols.size(),nv=nr+nc;
      if(nv>60 || nv==0)return false;
      std::vector<uint64_t> adj(nv,0),closed(nv,0);
      for(size_t i=0;i<nv;++i)closed[i]=uint64_t(1)<<i;
      for(const auto &[r,c]:defects) {
        auto ri=std::lower_bound(active_rows.begin(),active_rows.end(),r)-active_rows.begin();
        auto ci=nr+(std::lower_bound(active_cols.begin(),active_cols.end(),c)-active_cols.begin());
        adj[ri]|=uint64_t(1)<<ci;adj[ci]|=uint64_t(1)<<ri;
        closed[ri]|=uint64_t(1)<<ci;closed[ci]|=uint64_t(1)<<ri;
      }
      size_t maxdeg=0;
      for(auto x:adj)maxdeg=std::max(maxdeg,size_t(__builtin_popcountll(x)));
      // These two extension modes focus on states not already solvable by
      // ET2. The existing ET2 is independently tested as its own baseline.
      if(maxdeg<=2)return false;
      int hub=-1;
      std::vector<uint64_t> components;
      if(method==1 || method==2) {
        std::vector<int> good;
        for(size_t z=0;z<nv;++z) {
          bool ok=true;
          for(size_t v=0;v<nv;++v)if(v!=z) {
            const size_t d=__builtin_popcountll(adj[v])-
                           bool(adj[v]&(uint64_t(1)<<z));
            if(d>2){ok=false;break;}
          }
          if(ok)good.push_back(int(z));
        }
        if(good.empty())return false;
        if(method==1)hub=good.front(); // fixed first-index obstruction
        else hub=*std::max_element(good.begin(),good.end(),[&](int a,int b){
          return __builtin_popcountll(adj[a])<__builtin_popcountll(adj[b]);
        });
      } else if(method==4) {
        uint64_t visited=0;
        for(size_t v=0;v<nv;++v)if(!(visited&(uint64_t(1)<<v))) {
          uint64_t component=uint64_t(1)<<v;
          for(;;) {
            uint64_t newnodes=component;
            for(uint64_t rem=component;rem;rem&=rem-1)
              newnodes|=adj[__builtin_ctzll(rem)];
            if(newnodes==component)break;
            component=newnodes;
          }
          visited|=component;
          components.push_back(component);
          if(size_t(__builtin_popcountll(component))>config_.v56_component_cap)
            return false;
        }
      } else throw std::logic_error("V56 invalid terminal choice");
      const uint64_t all=(uint64_t(1)<<nv)-1;
      const uint64_t rowmask=(uint64_t(1)<<nr)-1;
      const uint64_t colmask=all & ~rowmask;
      const bool has_isolated_row=nr<paths.size();
      const bool has_isolated_col=nc<universe.size();
      std::vector<uint64_t> solutions;
      solutions.reserve(std::min(maxout+1,size_t(64)));
      auto dfs=[&](auto&& self,uint64_t target,uint64_t selected,
                   uint64_t dominated,uint64_t forbidden,
                   std::vector<uint64_t>& out)->void {
        if(overflow)return;
        if(dominated==target) {
          out.push_back(selected);
          if(out.size()>maxout)overflow=true;
          return;
        }
        const uint64_t allowed=target&~forbidden;
        const uint64_t remain=target&~dominated;
        for(uint64_t m=remain;m;m&=m-1)
          if(!(closed[__builtin_ctzll(m)]&allowed))return;
        const unsigned v=__builtin_ctzll(remain);
        uint64_t choices=closed[v]&allowed,earlier=0;
        while(choices && !overflow) {
          uint64_t bit=choices & (~choices+1);
          unsigned i=__builtin_ctzll(bit);
          self(self,target,selected|bit,dominated|closed[i],
               forbidden|earlier|(closed[i]&~bit),out);
          earlier|=bit;
          choices&=choices-1;
        }
      };
      if(hub>=0) {
        const uint64_t bit=uint64_t(1)<<hub;
        // Two disjoint MIS classes: selecting hub, or excluding hub.
        // The second class still must dominate hub to be globally maximal.
        ++stats_.v56_pivot_branches;
        dfs(dfs,all,bit,closed[hub],adj[hub],solutions);
        dfs(dfs,all,0,0,bit,solutions);
      } else if(method==4) {
        // Component decomposition: the MIS family of a disjoint union is the
        // Cartesian product of the MIS families of its components.
        solutions.push_back(0);
        for(uint64_t component:components) {
          std::vector<uint64_t> local;
          dfs(dfs,component,0,0,0,local);
          if(overflow || local.empty() ||
             solutions.size()>maxout/local.size()) {overflow=true;break;}
          std::vector<uint64_t> next;
          next.reserve(solutions.size()*local.size());
          for(uint64_t lhs:solutions)for(uint64_t rhs:local)
            next.push_back(lhs|rhs);
          solutions.swap(next);
        }
      } else dfs(dfs,all,0,0,0,solutions);
      if(overflow) {++stats_.v56_cap_reject;return false;}
      outputs.reserve(solutions.size());
      for(auto selected:solutions) {
        // Empty-side maximal independent sets do not define bicliques.
        if(!((has_isolated_row || (selected&rowmask)) &&
             (has_isolated_col || (selected&colmask))))continue;
        VidList cols;
        cols.reserve(universe.size());
        size_t ci=0;
        const uint64_t mask=selected>>nr;
        for(size_t j=0;j<universe.size();++j) {
          if(ci<active_cols.size() && active_cols[ci]==j) {
            if(mask&(uint64_t(1)<<ci))cols.push_back(universe[j]);
            ++ci;
          } else cols.push_back(universe[j]);
        }
        if(!cols.empty())outputs.push_back(std::move(cols));
      }
    }
    // Commit only after verification, size cap, and enumeration all succeed.
    ++stats_.v56_hits;
    ++stats_.et_hits;
    stats_.v56_outputs+=outputs.size();
    for(const VidList &cols:outputs) {
      ResultTreeNode *at=nullptr;
      for(vid_t c:cols) at=AppendMISColumn(at,c);
      if(!at)throw std::logic_error("V56 empty terminal output");
      if(at->is_end)++duplicated_cnt_;
      else {at->is_end=true;++stats_.et_generated_lower_layers;}
    }
    return true;
  }

  // V55 experimental TG2. We only choose a canonical *initial* prefix of
  // candidate terminal paths. The existing suffix-first traversal and its
  // ownership invariant are intentionally unchanged. All results are prepared
  // BEFORE deferring anything; cap failures fall back without mutation.
  // For a degree<=2 bipartite complement, MIS of the graph is bijective with
  // distinct nonempty intersections of nonempty path subsets. Isolated rows
  // and columns are mandatory vertices in every MIS. The exact bounded MIS
  // routine below reproduces the ET2 dominance/forbidden invariant, with the
  // global Result Tree only touched after processing the suffix.
  TGPrefixPlan BuildTG2PrefixPlan(NeighborTreeNode *root) {
    TGPrefixPlan plan;
    if (!config_.tg || !config_.et || config_.kappa != 2 || !config_.tg2_prefix) return plan;
    ++stats_.tg2_plan_attempts;
    if (root->is_end) return plan;
    const size_t total = root->end_count;
    const size_t minprefix = std::max<size_t>(3, config_.tg_prefix_min);
    if (total <= minprefix || (config_.tg_min_family && total < config_.tg_min_family)) return plan;
    const size_t cap = std::min<size_t>({config_.tg_prefix_cap, total-1, size_t(64)});
    if (cap < minprefix) return plan;
    // Necessary bound: any prefix with >=3 rows, degree <=2 implies all
    // columns occur in the union of its first 3 rows.
    std::vector<VidList> paths;
    std::vector<NeighborTreeNode*> ends;
    VidList cur;
    paths.reserve(cap+1); ends.reserve(cap+1);
    for (const auto &[id, child] : root->children) {
      CollectFirstCandidateEnds(child.get(), cur, paths, ends, cap+1);
      if (paths.size() >= cap+1) break;
    }
    if (paths.size() < minprefix) return plan;
    VidList universe = paths[0];
    for (size_t i=1; i<3; ++i) {
      VidList merged;
      std::set_union(universe.begin(),universe.end(), paths[i].begin(),paths[i].end(),
                     std::back_inserter(merged));
      universe.swap(merged);
    }
    if (universe.empty()) return plan;
    if (universe.size() > paths[0].size()+2 ||
        universe.size() > paths[1].size()+2 ||
        universe.size() > paths[2].size()+2) return plan;
    std::vector<unsigned char> deg(universe.size(),0);
    std::vector<std::pair<size_t,size_t>> defects;
    size_t accepted=0, active_last=0;
    bool has_full_row = false;
    for (size_t r=0; r<cap; ++r) {
      // Transactional row admission: no count update on rejected row.
#ifdef MBE_TG2_STACK_MISSES
      // At most two omissions are admissible; avoid allocating a small vector
      // for every scanned path. This preserves the exact candidate predicate.
      size_t misses[2];
      size_t nmiss=0;
#else
      std::vector<size_t> misses;
#endif
      size_t j=0;
      bool invalid=false;
      for (size_t i=0;i<universe.size();++i) {
        if (j<paths[r].size() && paths[r][j]==universe[i]) {++j;continue;}
        if (j<paths[r].size() && paths[r][j]<universe[i]) {invalid=true;break;}
        if (deg[i]>=2) {invalid=true;break;}
#ifdef MBE_TG2_STACK_MISSES
        if (nmiss==2) {invalid=true;break;}
        misses[nmiss++]=i;
#else
        misses.push_back(i);
        if (misses.size()>2) {invalid=true;break;}
#endif
      }
      if (j!=paths[r].size()) invalid=true;
#ifdef MBE_TG2_STACK_MISSES
      if (invalid || defects.size()+nmiss>config_.et2_max_defects) break;
      for (size_t k=0;k<nmiss;++k) {
        size_t c=misses[k];++deg[c];defects.emplace_back(r,c);
      }
      if (nmiss==0) has_full_row=true;
#else
      if (invalid || defects.size()+misses.size()>config_.et2_max_defects) break;
      for (size_t c: misses) {++deg[c];defects.emplace_back(r,c);}
      if (misses.empty()) has_full_row=true;
#endif
      accepted=r+1;
      active_last=defects.size();
    }
    if (accepted<minprefix) return plan;
    if (config_.tg2_require_nonmatching &&
        std::none_of(deg.begin(),deg.end(),[](unsigned char x){return x==2;}) &&
        // Two omissions in one row also give a complement degree-2 vertex.
        (defects.size()<2 || [&](){
          for(size_t i=1;i<defects.size();++i)
            if(defects[i].first==defects[i-1].first)return false;
          return true;
        }())) return plan;
    ++stats_.tg2_candidate_prefixes;
    // Build active complement vertices and exact MIS BEFORE setting deferred.
    std::vector<size_t> rows, cols;
    rows.reserve(defects.size());cols.reserve(defects.size());
    for (auto [r,c]:defects){rows.push_back(r);cols.push_back(c);}
    std::sort(rows.begin(),rows.end()); rows.erase(std::unique(rows.begin(),rows.end()),rows.end());
    std::sort(cols.begin(),cols.end()); cols.erase(std::unique(cols.begin(),cols.end()),cols.end());
    const size_t nr=rows.size(), nc=cols.size(), nv=nr+nc;
    if (nv>60) {++stats_.tg2_cap_rejections;return plan;}
    std::vector<uint64_t> closed(nv);
    for(size_t i=0;i<nv;i++)closed[i]=uint64_t(1)<<i;
    for(auto [r,c]:defects) {
      const size_t ri=std::lower_bound(rows.begin(),rows.end(),r)-rows.begin();
      const size_t ci=nr+(std::lower_bound(cols.begin(),cols.end(),c)-cols.begin());
      closed[ri]|=uint64_t(1)<<ci;closed[ci]|=uint64_t(1)<<ri;
    }
    const uint64_t all = nv ? ((uint64_t(1)<<nv)-1) : 0;
    const uint64_t rm = nr ? ((uint64_t(1)<<nr)-1) : 0;
    const uint64_t cm = all & ~rm;
    std::vector<uint64_t> mis;
    mis.reserve(std::min<size_t>(config_.et2_max_mis,64));
    bool overflow=false;
    auto enumerate=[&](auto&& self,uint64_t selected,uint64_t dominated,uint64_t forbidden)->void {
      if(overflow)return;
      if(dominated==all) {
        const bool row_present=has_full_row || (selected&rm);
        const bool col_present=(universe.size()>nc) || (selected&cm);
        if(row_present && col_present) {
          if(mis.size()>=config_.et2_max_mis){overflow=true;return;}
          mis.push_back(selected);
        }
        return;
      }
      const uint64_t allowed=all&~forbidden,undom=all&~dominated;
      for(uint64_t b=undom;b;b&=b-1) {
        const unsigned v=__builtin_ctzll(b);
        if(!(closed[v]&allowed))return;
      }
      const unsigned v=__builtin_ctzll(undom);
      uint64_t opts=closed[v]&allowed,earlier=0;
      while(opts&&!overflow) {
        const uint64_t choice=opts&(~opts+1);
        const unsigned w=__builtin_ctzll(choice);
        self(self,selected|choice,dominated|closed[w],
             forbidden|earlier|(closed[w]&~choice));
        earlier|=choice;opts&=opts-1;
      }
    };
    enumerate(enumerate,0,0,0);
    if(overflow){++stats_.tg2_cap_rejections;return plan;}
    std::vector<VidList> outputs;
    outputs.reserve(mis.size());
    for(uint64_t selected:mis) {
      const uint64_t kept=selected>>nr;
      VidList result;
      size_t ci=0;
      for(size_t i=0;i<universe.size();++i){
        bool keep=true;
        if(ci<nc && cols[ci]==i){keep=bool(kept&(uint64_t(1)<<ci));++ci;}
        if(keep)result.push_back(universe[i]);
      }
      if(!result.empty())outputs.push_back(std::move(result));
    }
    // A prefix must be proper; the original TG's suffix-first ownership
    // logic depends on having at least one non-deferred suffix endpoint.
    if(accepted>=total)return plan;
    for(size_t i=0;i<accepted;++i)ends[i]->tg_deferred=true;
    plan.active=true;plan.two_biplex=true;
    plan.two_biplex_outputs=std::move(outputs);
    plan.prefix_paths=accepted;
    plan.last_deferred_preorder=ends[accepted-1]->dfs_idx.first;
    ++stats_.tg2_prefix_hits;
    stats_.tg2_deferred_paths+=accepted;
    stats_.tg2_mis_outputs+=plan.two_biplex_outputs.size();
    bool nonmatching=false;
    for(size_t i=0;i<nv;i++)if(__builtin_popcountll(closed[i])>2){nonmatching=true;break;}
    if(nonmatching)++stats_.tg2_nonmatching_hits;
    ++stats_.tg_partition_hits;
    stats_.tg_deferred_paths+=accepted;
    if(accepted==2)++stats_.tg_prefix2_hits;else ++stats_.tg_prefix_ge3_hits;
    return plan;
  }

  void ResolveTG2Prefix(const TGPrefixPlan &plan) {
    for(const VidList &cols:plan.two_biplex_outputs) {
      ResultTreeNode *node=nullptr;
      for(vid_t c:cols)node=AppendMISColumn(node,c);
      if(!node)throw std::logic_error("V55 TG2 emitted empty lower-side path");
      if(node->is_end){++duplicated_cnt_;++stats_.tg2_emit_duplicate;}
      else{node->is_end=true;++stats_.et_generated_lower_layers;++stats_.tg2_emit_new;}
    }
  }

  // Partition-oriented one-sided TG (v5).
  //
  // The 2026 two-sided IPS rule first separates terminal-compatible candidates
  // from the candidates that still obstruct the stopping condition, and then
  // branches only where an obstruction can be removed.  In MBET we cannot
  // arbitrarily choose a pivot: a candidate path is allowed to derive
  // intersections only with paths before it in the canonical DFS order.
  // Therefore the ownership-safe analogue is a *canonical prefix partition*.
  //
  // If the first k candidate paths already form an exact matching terminal,
  // we defer their own recursive expansions.  Paths after the prefix are kept
  // in the ordinary MBET search.  Any intersection containing a suffix path is
  // still owned by its latest (suffix) path and therefore remains reachable;
  // intersections involving only the prefix are batch-resolved by ET after the
  // suffix search finishes.  No global vertex order or DFS child order changes.
  // Lazy TG v12: reuse per-engine verification scratch storage across states.
  // The canonical prefix test and deferral semantics remain unchanged.
  // The prefix/suffix rule and all deferred ownership semantics are unchanged.
  TGPrefixPlan BuildTGPrefixPlan(NeighborTreeNode *root) {
#ifdef MBE_V29_PROFILE
    auto v29_phase_watch = DebugTimer<42>::AutoWatch();
#endif
    TGPrefixPlan plan;
    if (!config_.tg || !config_.et || (config_.kappa != 1 && config_.kappa != 2)) return plan;

    static constexpr size_t kTGPrefixCap = 64;
    size_t min_prefix = std::max<size_t>(2, config_.tg_prefix_min);
    const size_t prefix_cap = std::min<size_t>(kTGPrefixCap, std::max<size_t>(2, config_.tg_prefix_cap));
    ++stats_.tg_gate_attempts;

    // Use the already-maintained subtree counts; no intersection or allocation.
    // V47: root end_count is maintained during both initial build_end and
    // recursive dfs_reduce. It is exactly the sum of terminal counts of the
    // root's children (dummy root is never a terminal). No semantic change.
    size_t total_ends = 0;
    if (config_.tg_cached_root_count) {
      total_ends = root->end_count;
    } else {
      for (const auto &[id, child] : root->children) total_ends += child->end_count;
    }
    // v37: old 3-path TG is the fallback when the family is too small for
    // profitable 2-path TG. end_count is already maintained, no graph probes.
    if (min_prefix == 2 && total_ends < config_.tg_two_min_family) {
      min_prefix = 3;
      if (config_.tg_two_min_family > 3) ++stats_.tg_two_small_family_skips;
    }
    if (total_ends <= min_prefix) return plan;
    if (config_.tg_min_family && total_ends < config_.tg_min_family) {
      ++stats_.tg_family_gate_skips;
      return plan;
    }
    ++stats_.tg_metadata_passed;
    const bool five_path_family = (total_ends == 5);
    if (five_path_family) ++stats_.tg_five_path_attempts;

    // v7: consume complete terminal subtrees from maintained length metadata.
    // Only descend into the boundary subtree containing the kth terminal.
    // The canonical DFS end order is identical to CollectFirstCandidateEnds.
    size_t seen = 0;
    size_t lo = std::numeric_limits<size_t>::max(), hi = 0;
    bool length_failed = false;
    auto add_lengths = [&](size_t mn, size_t mx, size_t count) {
      lo = std::min(lo, mn);
      hi = std::max(hi, mx);
      seen += count;
      if (hi - lo > 1) length_failed = true;
    };
    auto scan = [&](auto &&self, const NeighborTreeNode *node, size_t depth) -> void {
      if (length_failed || seen == min_prefix || !node->end_count) return;
      const size_t remaining = min_prefix - seen;
      if (node->end_count <= remaining) {
        // end lengths are measured from this node, including the node itself.
        add_lengths(depth + node->min_end_len - 1,
                    depth + node->max_end_len - 1, node->end_count);
        return;
      }
      if (node->is_end) add_lengths(depth, depth, 1);
      if (length_failed || seen == min_prefix) return;
      for (const auto &[id, child] : node->children) {
        self(self, child.get(), depth + 1);
        if (length_failed || seen == min_prefix) break;
      }
    };
    for (const auto &[id, child] : root->children) {
      scan(scan, child.get(), 1);
      if (length_failed || seen == min_prefix) break;
    }
    if (length_failed || seen < min_prefix) return plan;
    ++stats_.tg_length_passed;

    // v11: stream canonical end paths into the verifier.  The first two
    // paths define the fixed universe.  Subsequent paths are checked as they
    // are visited, without materializing a vector of path vectors.
    ++stats_.tg_partition_checks;
    ++stats_.tg_exact_checks;
    const size_t max_prefix = std::min(prefix_cap, total_ends - 1);
    // This engine searches serially. BuildTGPrefixPlan completes before Find
    // creates recursive descendants, so reusable member scratch is safe here.
    // Avoid three heap allocations in each of the many exact-check states.
    VidList &current = tg_scratch_current_;
    VidList &first = tg_scratch_first_;
    std::vector<unsigned char> &miss_count = tg_scratch_misses_;
    current.clear();
    first.clear();
    miss_count.clear();
    if (current.capacity() < hi) current.reserve(hi);
    if (first.capacity() < hi) first.reserve(hi);
    NeighborTreeNode *accepted_ends[kTGPrefixCap];
    size_t visited = 0, prefix = 0;
    auto add_row = [&](const VidList &p) -> bool {
      size_t i = 0, j = 0, misses = 0, miss_pos = 0;
      while (j < p.size() && i < plan.universe.size()) {
        if (p[j] == plan.universe[i]) { ++i; ++j; }
        else if (p[j] < plan.universe[i]) return false;
        else {
          ++misses; miss_pos = i++;
          if (misses > 1) {
#ifdef MBE_ET13_DIAG
            ++et13_.rejected_many_misses;
#endif
            return false;
          }
        }
      }
      if (j < p.size()) return false;
      while (i < plan.universe.size()) {
        ++misses; miss_pos = i++;
        if (misses > 1) return false;
      }
      if (misses == 0) plan.has_full_row = true;
      else {
        if (++miss_count[miss_pos] > 1) {
#ifdef MBE_ET13_DIAG
          ++et13_.rejected_collision;
#endif
          return false;
        }
        plan.defects.emplace_back(plan.universe[miss_pos]);
      }
      return true;
    };
    auto accept_end = [&](NeighborTreeNode *end) -> bool {
      ++visited;
      if (visited == 1) {
        first.assign(current.begin(), current.end());
        accepted_ends[prefix++] = end;
        return true;
      }
      if (visited == 2) {
        // Necessary condition for a matching terminal on two rows.
        size_t i = 0, j = 0, only0 = 0, only1 = 0;
        while (i < first.size() && j < current.size()) {
          if (first[i] == current[j]) { ++i; ++j; }
          else if (first[i] < current[j]) {
            if (++only0 > 1) return false;
            ++i;
          } else {
            if (++only1 > 1) return false;
            ++j;
          }
        }
        if (only0 + first.size() - i > 1 ||
            only1 + current.size() - j > 1) {
          return false;
        }
        plan.universe.reserve(first.size() + current.size());
        std::set_union(first.begin(), first.end(), current.begin(), current.end(),
                       std::back_inserter(plan.universe));
        if (plan.universe.empty()) return false;
        miss_count.resize(plan.universe.size(), 0);
        if (!add_row(first) || !add_row(current)) {
          return false;
        }
        accepted_ends[prefix++] = end;
        return prefix < max_prefix;
      }
      if (!add_row(current)) return false;
      accepted_ends[prefix++] = end;
      return prefix < max_prefix;
    };
    auto visit = [&](auto &&self, NeighborTreeNode *node) -> bool {
      current.emplace_back(node->vid);
      if (node->is_end && !accept_end(node)) {
        current.pop_back();
        return false;
      }
      for (const auto &[id, child] : node->children) {
        if (!self(self, child.get())) {
          current.pop_back();
          return false;
        }
      }
      current.pop_back();
      return true;
    };
    for (const auto &[id, child] : root->children) {
      if (!visit(visit, child.get())) break;
    }
    if (prefix < min_prefix) return TGPrefixPlan{};
    // The observed suffix is bounded by the configured lookahead cap,
    // rather than inferred from the complete candidate family.
    const size_t observed_suffix = std::min(prefix_cap + 1, total_ends) - prefix;
    if (prefix == 3 && observed_suffix > 2) return TGPrefixPlan{};
    for (size_t i = 0; i < prefix; ++i) accepted_ends[i]->tg_deferred = true;
    plan.active = true;
    plan.prefix_paths = prefix;
    plan.last_deferred_preorder = accepted_ends[prefix - 1]->dfs_idx.first;
    ++stats_.tg_partition_hits;
    if (prefix == 2) {
      ++stats_.tg_prefix2_hits;
#ifdef MBE_ET13_DIAG
      const size_t b = total_ends==3 ? 0 : total_ends==4 ? 1 : total_ends<8 ? 2
                      : total_ends<16 ? 3 : total_ends<64 ? 4 : 5;
      ++stats_.tg_two_hit_family_hist[b];
#endif
    }
    else ++stats_.tg_prefix_ge3_hits;
    if (five_path_family) ++stats_.tg_five_path_hits;
    stats_.tg_deferred_paths += prefix;
    return plan;
  }

  // V49: consume TG's canonical terminal rows *while* the mandatory dfs_pre
  // traversal generates the DFS preorder/jump links.  No second prefix tree
  // traversal is needed. The exact same sorted-path matching conditions and
  // defer/resolve ownership rule are used as BuildTGPrefixPlan.
  struct TGPreorderBuilder {
    MBETFastConfig const &cfg;
    MBETFastStats &stats;
    VidList &row, &first;
    std::vector<unsigned char> &miss_count;
    TGPrefixPlan plan;
    NeighborTreeNode *ends[64]{};
    size_t total = 0, min_prefix = 0, max_prefix = 0, prefix = 0;
    size_t collected = 0, min_depth = SIZE_MAX, max_depth = 0;
    bool done = true, checking = false, five = false;

    TGPreorderBuilder(const MBETFastConfig &c, MBETFastStats &s,
        VidList &scratch_row, VidList &scratch_first,
        std::vector<unsigned char> &scratch_misses,
        NeighborTreeNode *root)
      : cfg(c), stats(s), row(scratch_row), first(scratch_first),
        miss_count(scratch_misses) {
      ++stats.tg_gate_attempts;
      for (auto &[id, child] : root->children) total += child->end_count;
      min_prefix = std::max<size_t>(2, cfg.tg_prefix_min);
      if (min_prefix == 2 && total < cfg.tg_two_min_family) {
        min_prefix = 3;
        if (cfg.tg_two_min_family > 3) ++stats.tg_two_small_family_skips;
      }
      if (total <= min_prefix) return;
      if (cfg.tg_min_family && total < cfg.tg_min_family) {
        ++stats.tg_family_gate_skips;
        return;
      }
      ++stats.tg_metadata_passed;
      five = total == 5;
      if (five) ++stats.tg_five_path_attempts;
      const size_t cap = std::min<size_t>(64, std::max<size_t>(2, cfg.tg_prefix_cap));
      max_prefix = std::min(cap, total - 1);
      done = false;
    }

    void extract_row(NeighborTreeNode *end, size_t depth) {
      row.resize(depth);
      for (size_t i=depth; i; --i) {
        if (!end) throw std::logic_error("V49 invalid candidate parent path");
        row[i-1] = end->vid;
        end = end->parent;
      }
    }

    bool add_row(const VidList &r) {
      size_t i=0,j=0,misses=0,miss_pos=0;
      while (j<r.size() && i<plan.universe.size()) {
        if (r[j]==plan.universe[i]) { ++i; ++j; }
        else if (r[j]<plan.universe[i]) return false;
        else {
          ++misses; miss_pos=i++;
          if (misses>1) return false;
        }
      }
      if (j<r.size()) return false;
      while (i<plan.universe.size()) {
        ++misses; miss_pos=i++;
        if (misses>1) return false;
      }
      if (!misses) plan.has_full_row=true;
      else {
        if (++miss_count[miss_pos]>1) return false;
        plan.defects.push_back(plan.universe[miss_pos]);
      }
      return true;
    }

    bool accept(NeighborTreeNode *end, size_t depth) {
      ++stats.tg_fused_exact_rows;
      extract_row(end,depth);
      if (prefix == 0) {
        first.assign(row.begin(),row.end());
        ends[prefix++]=end;
        return true;
      }
      if (prefix == 1) {
        size_t i=0,j=0,only0=0,only1=0;
        while (i<first.size() && j<row.size()) {
          if (first[i]==row[j]) { ++i; ++j; }
          else if (first[i]<row[j]) {
            if (++only0>1) return false;
            ++i;
          } else {
            if (++only1>1) return false;
            ++j;
          }
        }
        if (only0+first.size()-i>1 || only1+row.size()-j>1) return false;
        plan.universe.reserve(first.size()+row.size());
        std::set_union(first.begin(),first.end(),row.begin(),row.end(),
                       std::back_inserter(plan.universe));
        if (plan.universe.empty()) return false;
        miss_count.assign(plan.universe.size(),0);
        // The first row was saved separately, and must be verified before
        // the second row using the same missing-column collision condition.
        if (!add_row(first) || !add_row(row)) return false;
        ends[prefix++]=end;
        return true;
      }
      if (!add_row(row)) return false;
      ends[prefix++]=end;
      return true;
    }

    // dfs_pre visits these endpoints in exactly the same preorder as TG's
    // previous canonical-prefix visitor. It can stop observing at any time;
    // dfs_pre itself MUST always finish building the global jump links.
    void observe(NeighborTreeNode *end, size_t depth) {
      if (done) return;
      ++stats.tg_fused_terminal_visits;
      if (!checking) {
        ends[collected++]=end;
        min_depth=std::min(min_depth,depth);
        max_depth=std::max(max_depth,depth);
        if (max_depth-min_depth>1) {
          ++stats.tg_fused_length_rejected;
          done=true;
          return;
        }
        if (collected<min_prefix) return;
        checking=true;
        ++stats.tg_length_passed;
        ++stats.tg_exact_checks;
        ++stats.tg_partition_checks;
        for (size_t i=0;i<collected;i++) {
          auto *item=ends[i];
          size_t len=0;
          for (auto *cur=item;cur;cur=cur->parent) ++len;
          if (!accept(item,len)) { done=true; break; }
        }
        if (prefix==max_prefix) done=true;
        return;
      }
      if (!accept(end,depth) || prefix==max_prefix) done=true;
    }

    TGPrefixPlan finish() {
      if (prefix<min_prefix) return TGPrefixPlan{};
      const size_t cap=std::min<size_t>(64,std::max<size_t>(2,cfg.tg_prefix_cap));
      const size_t observed_suffix=std::min(cap+1,total)-prefix;
      if (prefix==3 && observed_suffix>2) return TGPrefixPlan{};
      for (size_t i=0;i<prefix;i++) ends[i]->tg_deferred=true;
      plan.active=true;
      plan.prefix_paths=prefix;
      plan.last_deferred_preorder=ends[prefix-1]->dfs_idx.first;
      ++stats.tg_partition_hits;
      if (prefix==2) {
        ++stats.tg_prefix2_hits;
#ifdef MBE_ET13_DIAG
        const size_t b=total==3?0:total==4?1:total<8?2:total<16?3:total<64?4:5;
        ++stats.tg_two_hit_family_hist[b];
#endif
      } else ++stats.tg_prefix_ge3_hits;
      if (five) ++stats.tg_five_path_hits;
      stats.tg_deferred_paths+=prefix;
      return std::move(plan);
    }
  };

  // ET is intentionally identical for TG on/off.  This keeps the ablation
  // clean: any change in ET reachability is caused by candidate organization,
  // not by a different terminal verifier.
  // V59: separate the matching verifier from kappa dispatch. Matching
  // complements are a subset of 2-biplex, so this solver is valid when
  // kappa=2 as well; it still enumerates the exact same full-family closure.
  bool TryMatchingTerminal(NeighborTreeNode *root, SharedTGHint *hint = nullptr) {
    et_auto_skipped_last_ = false;
#ifdef MBE_V29_PROFILE
    auto v29_phase_watch = DebugTimer<41>::AutoWatch();
#endif
    if (!config_.et || !config_.et_root_enabled || (config_.kappa != 1 && config_.kappa != 2)) return false;
    // On-line ET admission control: a failed admission NEVER prunes a branch;
    // it simply falls through to ordinary, unmodified Find() search.
    // Decisions depend on completed full verifications in prior states, not
    // on a graph-specific whitelist or an offline/precomputed dataset profile.
    if (config_.et_profit_auto) {
      ++et_auto_find_calls_;
      if (et_auto_pause_until_) {
        if (et_auto_find_calls_ < et_auto_pause_until_) {
          ++stats_.et_auto_skipped_calls;
          et_auto_skipped_last_ = true;
          return false;
        }
        et_auto_pause_until_ = 0;
        et_auto_base_checks_ = stats_.et_checks;
        et_auto_base_new_ = stats_.et_generated_lower_layers;
        ++stats_.et_auto_probes;
      }
      const size_t verified = stats_.et_checks - et_auto_base_checks_;
      if (verified >= config_.et_auto_window) {
        const size_t productive = stats_.et_generated_lower_layers - et_auto_base_new_;
        if (productive * 100 < config_.et_auto_yield_pct * verified) {
          et_auto_pause_until_ = et_auto_find_calls_ + config_.et_auto_pause;
          ++stats_.et_auto_pauses;
          ++stats_.et_auto_skipped_calls;
          et_auto_skipped_last_ = true;
          return false;
        }
        et_auto_base_checks_ = stats_.et_checks;
        et_auto_base_new_ = stats_.et_generated_lower_layers;
      }
    }
#ifdef MBE_ET13_DIAG
    ++et13_.try_calls;
#endif
    // Every legal terminal row misses at most ONE column of the union.
    // Let a<b<c be three distinct first vertices.  A row beginning at c
    // misses a and b, hence no matching-terminal can have three root children.
    // If exactly two first vertices a<b occur, every row beginning at b
    // misses a and must contain every other union column; the b-branch
    // therefore has exactly one distinct terminal path.  These are
    // NECESSARY conditions only: on rejection, we run ordinary DFS.
    if (config_.et_root_shape_gate && root->children.size() >= 2) {
      bool impossible = root->children.size() > 2;
      if (!impossible) {
        auto it = root->children.begin();
        ++it;
        impossible = it->second->end_count > 1;
      }
      if (impossible) {
        ++stats_.et_root_gate_reject;
        return false;
      }
    }
    // V50: dummy-root metadata is already maintained by build_end / dfs_reduce.
    // The root's lengths include the dummy root (one extra level); shifting
    // both by one preserves the length span and max_len+1 cardinality rule.
    // Crucially this avoids revisiting every root child on every Find call.
    size_t quick_paths = 0;
    size_t min_len = std::numeric_limits<size_t>::max();
    size_t max_len = 0;
    // A recursive candidate dummy root can itself become is_end when
    // dfs_reduce observes a nonzero root sub_cnt. This EMPTY candidate path
    // is not included in ET's historical scan of root children. Its length
    // would also corrupt the cached minimum. Conservatively use the legacy
    // child scan in precisely those states (without changing ownership).
    const bool use_root_summary = config_.et_root_summary && !root->is_end;
    if (use_root_summary) {
      quick_paths = root->end_count;
      if (quick_paths) {
        if (root->min_end_len < 2 || root->max_end_len < 2)
          throw std::logic_error("V50 invalid nonempty root terminal lengths");
        min_len = root->min_end_len - 1;
        max_len = root->max_end_len - 1;
      }
    }
    if (!use_root_summary || config_.et_root_summary_verify) {
      size_t scanned_paths = 0;
      size_t scanned_min = std::numeric_limits<size_t>::max();
      size_t scanned_max = 0;
      for (const auto &[id, child] : root->children) {
        scanned_paths += child->end_count;
        if (child->end_count) {
          scanned_min = std::min(scanned_min, child->min_end_len);
          scanned_max = std::max(scanned_max, child->max_end_len);
        }
      }
      if (config_.et_root_summary_verify && use_root_summary &&
          (quick_paths != scanned_paths ||
           (quick_paths && (min_len != scanned_min || max_len != scanned_max))))
        throw std::logic_error("V50 root metadata disagreement in ET admission");
      if (!use_root_summary) {
        quick_paths = scanned_paths;
        min_len = scanned_min;
        max_len = scanned_max;
      }
    }
    if (quick_paths < config_.et_min_paths) {
#ifdef MBE_ET13_DIAG
      ++et13_.gate_few_paths;
#endif
      return false;
    }
    if (max_len > min_len + 1) {
#ifdef MBE_ET13_DIAG
      ++et13_.gate_length;
#endif
      return false;
    }
    // ET necessary condition, independent of thresholds and output state:
    // In a valid matching terminal every distinct row is either all of the
    // union columns or omits ONE DISTINCT column. Thus with maximum row
    // length M there can be at most M+1 distinct terminal rows. Rejecting a
    // larger family cannot drop an enumerated biclique: use ordinary DFS.
    // No path is collected, no graph intersection is performed here.
    if (config_.et_cardinality_gate && quick_paths > max_len + 1) {
#ifdef MBE_ET13_DIAG
      ++et13_.gate_cardinality;
#endif
      return false;
    }
    stats_.et_checks++;
#ifdef MBE_ET13_DIAG
    ++et13_.verified;
    et13_.terminal_paths_total += quick_paths;
    ++et13_.verified_paths_buckets[quick_paths<=3 ? 0 : quick_paths==4 ? 1 : quick_paths<8 ? 2 : quick_paths<16 ? 3 : 4];
    ET13TimedRegion et13_eligible_timer(et13_.eligible_wall_ns);
#endif

#if defined(MBE_ET_PAIR_GATE) && !defined(MBE_ET_STREAM)
    // Necessary two-row test. A valid matching 1-biplex gives each row
    // at most one non-neighbor in the union of ALL terminal paths. Thus the
    // difference of any two row paths contains at most one vertex per side.
    VidList first_path, path_scratch;
    std::vector<VidList> two_paths;
    std::vector<NeighborTreeNode*> two_ends;
    two_paths.reserve(2);
    two_ends.reserve(2);
    for (const auto &[id, child] : root->children) {
      CollectFirstCandidateEnds(child.get(), path_scratch, two_paths, two_ends, 2);
      if (two_paths.size() == 2) break;
    }
    if (two_paths.size() < 2) return false;
    const auto &a = two_paths[0], &b = two_paths[1];
    size_t i = 0, j = 0, only_a = 0, only_b = 0;
    while (i < a.size() && j < b.size()) {
      if (a[i] == b[j]) { ++i; ++j; }
      else if (a[i] < b[j]) { if (++only_a > 1) {
#ifdef MBE_ET13_DIAG
      ++et13_.rejected_pair;
#endif
      return false;
    } ++i; }
      else { if (++only_b > 1) {
#ifdef MBE_ET13_DIAG
      ++et13_.rejected_pair;
#endif
      return false;
    } ++j; }
    }
    if (only_a + a.size() - i > 1 || only_b + b.size() - j > 1) {
#ifdef MBE_ET13_DIAG
      ++et13_.rejected_pair;
#endif
      return false;
    }
#endif
#if defined(MBE_ET_STREAM)
    // Stream terminal paths without materializing vector<vector<vid_t>>.
    // For >=2 rows in a valid matching 1-biplex, every column occurs
    // in at least one of the first two rows. A new column appearing only
    // in later rows would be missing from both first rows (collision).
    // ET scratch is safe across Find recursion because verification finishes
    // before children are visited; matching resolution only visits result nodes.
    // The TG scratch is distinct because TG builds a deferred plan by value.
    VidList local_cur, local_first;
    std::vector<vid_t> local_universe, local_defects;
    std::vector<unsigned char> local_miss_count;
    VidList &cur = config_.et_reuse_scratch ? et_scratch_cur_ : local_cur;
    VidList &first = config_.et_reuse_scratch ? et_scratch_first_ : local_first;
    std::vector<vid_t> &universe = config_.et_reuse_scratch ? et_scratch_universe_ : local_universe;
    std::vector<vid_t> &defects = config_.et_reuse_scratch ? et_scratch_defects_ : local_defects;
    std::vector<unsigned char> &miss_count = config_.et_reuse_scratch ? et_scratch_misses_ : local_miss_count;
    cur.clear(); first.clear(); universe.clear(); defects.clear(); miss_count.clear();
    if (config_.et_reuse_scratch) ++stats_.et_scratch_attempts;
    size_t seen = 0;
    bool has_full_row = false;

    // Shared ET--TG path. TG's own admissibility restrictions are kept here;
    // if ET does not perform a full verification, existing TG is used instead.
    size_t hint_min = std::max<size_t>(2, config_.tg_prefix_min);
    const size_t hint_total = root->end_count;
    if (hint_min == 2 && hint_total < config_.tg_two_min_family) hint_min = 3;
    const size_t hint_cap = std::min<size_t>(64, std::min(config_.tg_prefix_cap,
                                                        hint_total ? hint_total-1 : 0));
    const bool track_hint = hint && config_.tg && hint_total > hint_min &&
                            hint_cap >= hint_min &&
                            (!config_.tg_min_family || hint_total >= config_.tg_min_family);
    if (track_hint) ++stats_.shared_et_streams;
    bool hint_snapshot = false;
    size_t accepted = 0;
    auto capture_row = [&](const NeighborTreeNode *end) {
      if (!track_hint || accepted >= hint_cap) return;
      hint->ends[accepted++] = const_cast<NeighborTreeNode *>(end);
      if (accepted == hint_cap) {
        hint->plan.universe = universe;
        hint->plan.defects = defects;
        hint->plan.has_full_row = has_full_row;
        hint_snapshot = true;
      }
    };

    auto add_row = [&](const VidList &p) -> bool {
      size_t i = 0, j = 0, missing = 0, missing_pos = 0;
      while (j < p.size() && i < universe.size()) {
        if (p[j] == universe[i]) { ++j; ++i; }
        else if (p[j] < universe[i]) {
          // A column not in the first-two-row union cannot be legal:
          // both first rows would have the same missing column.
#ifdef MBE_ET13_DIAG
          ++et13_.rejected_many_misses;
#endif
          return false;
        } else {
          if (++missing > 1) {
#ifdef MBE_ET13_DIAG
            ++et13_.rejected_many_misses;
#endif
            return false;
          }
          missing_pos = i++;
        }
      }
      if (j < p.size()) {
#ifdef MBE_ET13_DIAG
        ++et13_.rejected_many_misses;
#endif
        return false;
      }
      if (universe.size() - i > 1 - missing) {
#ifdef MBE_ET13_DIAG
        ++et13_.rejected_many_misses;
#endif
        return false;
      }
      if (universe.size() > i) {
        ++missing;
        missing_pos = universe.size() - 1;
      }
      if (!missing) has_full_row = true;
      else {
        if (++miss_count[missing_pos] > 1) {
#ifdef MBE_ET13_DIAG
          ++et13_.rejected_collision;
#endif
          return false;
        }
        defects.push_back(universe[missing_pos]);
      }
      return true;
    };

    auto on_end = [&](const NeighborTreeNode *end) -> bool {
      ++seen;
      if (seen == 1) {
        first.assign(cur.begin(), cur.end());
        capture_row(end);
        return true;
      }
      if (seen == 2) {
        // Early rejection before allocations of the entire candidate family.
        size_t i = 0, j = 0, only_first = 0, only_second = 0;
        while (i < first.size() && j < cur.size()) {
          if (first[i] == cur[j]) { ++i; ++j; }
          else if (first[i] < cur[j]) {
            if (++only_first > 1) {
#ifdef MBE_ET13_DIAG
            ++et13_.rejected_pair;
#endif
            return false;
          }
            ++i;
          } else {
            if (++only_second > 1) {
#ifdef MBE_ET13_DIAG
            ++et13_.rejected_pair;
#endif
            return false;
          }
            ++j;
          }
        }
        if (only_first + first.size() - i > 1 ||
            only_second + cur.size() - j > 1) {
#ifdef MBE_ET13_DIAG
          ++et13_.rejected_pair;
#endif
          return false;
        }
        universe.reserve(first.size() + cur.size());
        std::set_union(first.begin(), first.end(), cur.begin(), cur.end(),
                       std::back_inserter(universe));
        if (universe.empty()) {
#ifdef MBE_ET13_DIAG
          ++et13_.rejected_empty_universe;
#endif
          return false;
        }
        miss_count.resize(universe.size(), 0);
        if (!add_row(first) || !add_row(cur)) return false;
        capture_row(end);
        return true;
      }
      if (!add_row(cur)) return false;
      capture_row(end);
      return true;
    };

    auto visit = [&](auto &&self, const NeighborTreeNode *node) -> bool {
      cur.emplace_back(node->vid);
      if (node->is_end && !on_end(node)) {
        cur.pop_back();
        return false;
      }
      for (const auto &[id, child] : node->children) {
        if (!self(self, child.get())) {
          cur.pop_back();
          return false;
        }
      }
      cur.pop_back();
      return true;
    };
    bool et_stream_failed = false;
    for (const auto &[id, child] : root->children) {
      if (!visit(visit, child.get())) {
        et_stream_failed = true;
        break;
      }
    }
    if (et_stream_failed) {
      // ET has already proved that the first `accepted` canonical paths are
      // matching compatible. Share them with TG only if the original TG
      // accept rule would also stop at exactly that prefix.
      if (track_hint && accepted >= hint_min) {
        const size_t observed_suffix = std::min(config_.tg_prefix_cap + 1,
                                                 hint_total) - accepted;
        if (!(accepted == 3 && observed_suffix > 2)) {
          if (!hint_snapshot) {
            // ET is returning immediately: transfer ownership of the already
            // validated buffers, rather than copy them for the TG plan.
            hint->plan.universe = std::move(universe);
            hint->plan.defects = std::move(defects);
            hint->plan.has_full_row = has_full_row;
          }
          hint->accepted = accepted;
          hint->plan.prefix_paths = accepted;
          hint->plan.active = true;
          ++stats_.shared_prefix_candidates;
        }
      }
      return false;
    }
    if (seen < 2) {
#ifdef MBE_ET13_DIAG
      ++et13_.rejected_empty_paths;
#endif
      return false;
    }
    return ResolveMatchingTerminal(universe, std::move(defects), has_full_row);
#else
    std::vector<VidList> paths;
    VidList cur;
    {
#ifdef MBE_ET13_DIAG
      ET13TimedRegion et13_collect_timer(et13_.collect_wall_ns);
#endif
      for (const auto &[id, child] : root->children)
        CollectCandidatePaths(child.get(), cur, paths);
    }
    if (paths.empty()) {
#ifdef MBE_ET13_DIAG
      ++et13_.rejected_empty_paths;
#endif
      return false;
    }

    std::vector<vid_t> universe;
    for (const auto &p : paths) universe.insert(universe.end(), p.begin(), p.end());
    std::sort(universe.begin(), universe.end());
    universe.erase(std::unique(universe.begin(), universe.end()), universe.end());
    if (universe.empty()) {
#ifdef MBE_ET13_DIAG
      ++et13_.rejected_empty_universe;
#endif
      return false;
    }

    std::vector<vid_t> defects;
    std::vector<unsigned char> miss_count(universe.size(), 0);
    bool has_full_row = false;
    for (const auto &p : paths) {
      size_t i = 0, j = 0, misses = 0, miss_pos = 0;
      while (i < universe.size()) {
        while (j < p.size() && p[j] < universe[i]) ++j;
        if (j == p.size() || p[j] != universe[i]) {
          ++misses;
          miss_pos = i;
          if (misses > 1) {
#ifdef MBE_ET13_DIAG
            ++et13_.rejected_many_misses;
#endif
            return false;
          }
        }
        ++i;
      }
      if (misses == 0) {
        has_full_row = true;
      } else {
        if (++miss_count[miss_pos] > 1) {
#ifdef MBE_ET13_DIAG
          ++et13_.rejected_collision;
#endif
          return false;
        }
        defects.emplace_back(universe[miss_pos]);
      }
    }
    return ResolveMatchingTerminal(universe, std::move(defects), has_full_row);
#endif
  }

  bool TryBiplexTerminal(NeighborTreeNode *root, SharedTGHint *hint = nullptr) {
    if (config_.kappa == 2) return TryTwoBiplexTerminal(root);
    return TryMatchingTerminal(root, hint);
  }

  void build_traverse_order(size_t range_begin, size_t range_end, size_t nbr_index) {
    std::vector<vid_t> range_nbr;
    size_t out_range_cnt = 0;
    for (size_t i = range_begin; i < range_end; i++) {
      traverse_order_u_tmp_[i] = traverse_order_u_[i];
      auto &nbrs = bi_graph_.VertexU(traverse_order_u_[i])->neighbors;
      if (nbrs.size() <= nbr_index) {
        out_range_cnt++;
        continue;
      }
      auto nbr = nbrs[nbr_index]->vid;
      if (traverse_order_nbr_cnt_[nbr]++ == 0) {
        range_nbr.emplace_back(nbr);
      }
    }
    if (out_range_cnt == 0 && range_nbr.size() == 1) {
#ifdef MBETM
      traverse_order_v_range_[range_nbr.front()].emplace_back(range_begin, range_end - 1);
#endif
      traverse_order_nbr_cnt_[range_nbr.front()] = 0;
      build_traverse_order(range_begin, range_end, nbr_index + 1);
      return;
    }
    if (range_nbr.size() > 1) {
      std::sort(range_nbr.begin(), range_nbr.end());
    }
    size_t sub_range_begin = range_begin;
    for (auto &nbr : range_nbr) {
      auto cnt = traverse_order_nbr_cnt_[nbr];
      traverse_order_nbr_cnt_[nbr] = sub_range_begin;
      sub_range_begin += cnt;
    }
    for (size_t i = range_begin; i < range_end; i++) {
      auto &nbrs = bi_graph_.VertexU(traverse_order_u_tmp_[i])->neighbors;
      if (nbrs.size() <= nbr_index) {
        traverse_order_u_[sub_range_begin++] = traverse_order_u_tmp_[i];
      } else {
        traverse_order_u_[traverse_order_nbr_cnt_[nbrs[nbr_index]->vid]++] = traverse_order_u_tmp_[i];
      }
    }
    for (auto &pivot_nbr : range_nbr) {
      auto nbr = pivot_nbr;
      pivot_nbr = traverse_order_nbr_cnt_[nbr];
      traverse_order_nbr_cnt_[nbr] = 0;
    }
    sub_range_begin = range_begin;
    for (auto sub_range_end : range_nbr) {
      if (sub_range_end - sub_range_begin > 1) {
#ifdef MBETM
        auto &nbrs = bi_graph_.VertexU(traverse_order_u_[sub_range_begin])->neighbors;
        traverse_order_v_range_[nbrs[nbr_index]->vid].emplace_back(sub_range_begin, sub_range_end - 1);
#endif
        build_traverse_order(sub_range_begin, sub_range_end, nbr_index + 1);
      } else {
#ifdef MBETM
        auto &nbrs = bi_graph_.VertexU(traverse_order_u_[sub_range_begin])->neighbors;
        for (size_t i = nbr_index; i < nbrs.size(); i++) {
          traverse_order_v_range_[nbrs[i]->vid].emplace_back(sub_range_begin, sub_range_begin);
        }
#endif
      }
      sub_range_begin = sub_range_end;
    }
    for (; sub_range_begin < range_end - 1; sub_range_begin++) {
      traverse_order_u_tmp_[sub_range_begin] = static_cast<decltype(traverse_order_u_tmp_)::value_type>(-1);
    }
  }

  void build_end(NeighborTreeNode *node) {
    if (node->sub_cnt > 0) {
      node->is_end = true;
      node->sub_cnt = 0;
    }
    if (config_.et) {
      node->end_count = node->is_end ? 1 : 0;
      node->min_end_len = node->is_end ? 1 : std::numeric_limits<size_t>::max();
      node->max_end_len = node->is_end ? 1 : 0;
    }
    for (auto &[id, child] : node->children) {
      build_end(child.get());
      if (config_.et) {
        node->end_count += child->end_count;
        if (child->end_count) {
          node->min_end_len = std::min(node->min_end_len, child->min_end_len + 1);
          node->max_end_len = std::max(node->max_end_len, child->max_end_len + 1);
        }
      }
    }
  }

  void dfs_pre(NeighborTreeNode *node) {
#ifdef MBE_ET13_DIAG
    ++et13_.dfs_pre_nodes;
#endif
    dfs_cnt_++;
    node->dfs_idx.first = dfs_cnt_;
    auto vid = node->vid;
    if (cand_tree_prev_node_[vid].first != cand_tree_cnt_) {
      cand_tree_prev_node_[vid].first = cand_tree_cnt_;
      cand_tree_prev_node_[vid].second = nullptr;
    }
    node->prev = cand_tree_prev_node_[vid].second;
    cand_tree_prev_node_[vid].second = node;
    for (auto &[id, child] : node->children) {
      dfs_pre(child.get());
    }
    node->dfs_idx.second = dfs_cnt_;
  }

  // Dedicated fused traversal keeps the original dfs_pre hot path unchanged.
  void dfs_pre_fused(NeighborTreeNode *node, TGPreorderBuilder &builder, size_t depth) {
    dfs_cnt_++;
    node->dfs_idx.first=dfs_cnt_;
    const auto vid=node->vid;
    if (cand_tree_prev_node_[vid].first!=cand_tree_cnt_) {
      cand_tree_prev_node_[vid].first=cand_tree_cnt_;
      cand_tree_prev_node_[vid].second=nullptr;
    }
    node->prev=cand_tree_prev_node_[vid].second;
    cand_tree_prev_node_[vid].second=node;
    if (node->is_end && !builder.done) builder.observe(node,depth);
    for (auto &[id,child]:node->children) dfs_pre_fused(child.get(),builder,depth+1);
    node->dfs_idx.second=dfs_cnt_;
  }

  bool check_traverse_order_v_range(const std::pair<size_t, size_t> &pre_range, size_t idx) {
    if (idx >= traverse_order_v_range_idx_.size()) {
      return true;
    }
    const auto &ranges = traverse_order_v_range_[traverse_order_v_range_idx_[idx].first];
    for (auto &ri = traverse_order_v_range_idx_[idx].second; ri < ranges.size(); ri++) {
      if (ranges[ri].first >= pre_range.first && ranges[ri].second >= max_traverse_order_v_range_begin_) {
        if (ranges[ri].first > pre_range.second) {
          return false;
        }
        max_traverse_order_v_range_begin_ = std::max(max_traverse_order_v_range_begin_, ranges[ri].first);
        if (check_traverse_order_v_range(ranges[ri], idx + 1)) {
          return true;
        }
      }
    }
    return false;
  }

  void build_use(NeighborTreeNode *node, size_t depth, bool always_use = false) {
    if (always_use) {
      node->is_use = true;
    }
    if (node->is_end) {
      if (always_use) {
        node->is_res = true;
      } else {
        traverse_order_v_range_idx_.resize(depth);
        size_t d = depth;
        for (auto *s_node = node; s_node != nullptr; s_node = s_node->parent) {
          const auto &ranges = traverse_order_v_range_[s_node->vid];
          auto &ri = traverse_order_v_range_begin_[s_node->vid];
          while (ri < ranges.size() && ranges[ri].second <= traverse_order_u_pos_) {
            ri++;
          }
          traverse_order_v_range_idx_[--d] = {s_node->vid, ri};
        }
        max_traverse_order_v_range_begin_ = 0;
        if (!check_traverse_order_v_range({0, traverse_order_u_.size()}, 0)) {
          node->is_res = true;
          for (auto *s_node = node; s_node != nullptr; s_node = s_node->parent) {
            s_node->is_use = true;
          }
        }
      }
    }
    for (auto &[id, child] : node->children) {
      build_use(child.get(), depth + 1, always_use || node->is_res);
    }
  }

  void dfs_reduce(NeighborTreeNode *node) {
#ifdef MBE_ET13_DIAG
    ++et13_.dfs_reduce_nodes;
#endif
    size_t sum_child_sub_cnt = 0;
    for (const auto &[id, child] : node->children) sum_child_sub_cnt += child->sub_cnt;
    node->is_end = (sum_child_sub_cnt < node->sub_cnt);
    node->sub_cnt = 0;
    if (config_.et) {
      node->end_count = node->is_end ? 1 : 0;
      node->min_end_len = node->is_end ? 1 : std::numeric_limits<size_t>::max();
      node->max_end_len = node->is_end ? 1 : 0;
    }
    for (const auto &[id, child] : node->children) {
      dfs_reduce(child.get());
      if (config_.et) {
        node->end_count += child->end_count;
        if (child->end_count) {
          node->min_end_len = std::min(node->min_end_len, child->min_end_len + 1);
          node->max_end_len = std::max(node->max_end_len, child->max_end_len + 1);
        }
      }
    }
  }

  // v39: a candidate subtree is complete within the deferred canonical
  // prefix if all of its preorder nodes precede the last deferred terminal.
  // For the boundary terminal itself, a singleton terminal subtree is also
  // safe: it contains no non-deferred terminal below it.
  // Both predicates require only existing dfs_pre intervals and end_count.
  bool TGBlockFullyDeferred(const NeighborTreeNode *node) const {
    if (!tg_batch_boundary_preorder_ || !node->end_count) return false;
    return node->dfs_idx.second < tg_batch_boundary_preorder_ ||
      (node->end_count == 1 && node->is_end && node->tg_deferred);
  }

  // All terminals of this block have already been marked TG-deferred. The
  // previous per-terminal parent-chain increments are equivalent to setting
  // sub_cnt[u]=end_count[u] within the untouched subtree, and adding
  // end_count[block] once to every ancestor outside it. This is not a new
  // intersection; end_count was computed while constructing the candidate.
  void TGProcessDeferredBlock(ResultTreeNode *r_parent, NeighborTreeNode *block,
                              size_t depth) {
    const size_t terminals = block->end_count;
    ++stats_.tg_batch_blocks;
    stats_.tg_batch_ends += terminals;
    stats_.tg_batch_singletons += (terminals == 1);
    const size_t bin = terminals == 1 ? 0 : terminals == 2 ? 1 : terminals <= 4 ? 2
                     : terminals <= 8 ? 3 : terminals <= 16 ? 4 : 5;
    ++stats_.tg_batch_size_hist[bin];
    size_t ancestors = 0;
    for (NeighborTreeNode *p = block->parent; p; p = p->parent) {
      p->sub_cnt += terminals;
      ++ancestors;
    }
    if (terminals > 1) stats_.tg_batch_saved_ancestor_updates += (terminals-1)*ancestors;

    // Count-only mode preserves every Result Tree placeholder of v37.
    // Skip mode deliberately omits placeholders: they were not marked
    // is_end, and ResolveMatchingTerminal runs after the suffix search.
    const bool placeholders = (config_.tg_batch_mode == 1);
    const bool sparse = (config_.tg_batch_mode == 3);
    // V46: singleton deferred terminal blocks have no terminal descendants.
    // Their children all have end_count==0 and, since they were not DFS-visited,
    // retain sub_cnt==0. A block requiring no Result Tree placeholders can be
    // processed without recursively walking its dead descendants.
    if (sparse && terminals == 1 && block->is_end) {
      block->sub_cnt = 1;
      ++stats_.tg_batch_nodes;
      ++stats_.tg_batch_subcnt_writes;
      ++stats_.tg_batch_elided_result_visits;
      return;
    }
    auto walk = [&](auto &&self, ResultTreeNode *r, NeighborTreeNode *n) -> void {
      ++stats_.tg_batch_nodes;
#ifdef MBE_ET13_DIAG
      ++et13_.dfs_find_calls;
      if (n->is_end) {
        ++et13_.dfs_end_paths;
        et13_.dfs_subcnt_ancestor_updates += depth;
      } // Deferred block logical visits, not actual dfs_find calls.
#endif
#ifdef MBE_V29_PROFILE
      ++v29_dfs_find_calls_;
      v29_dfs_find_end_paths_ += n->is_end;
#endif
      if (n->end_count) {
        n->sub_cnt = n->end_count;
        ++stats_.tg_batch_subcnt_writes;
        stats_.tg_batch_saved_internal_updates += n->end_count - 1;
      }
      if (placeholders) {
        if (r == nullptr) {
          if (!result_tree_roots_[n->vid]) {
            result_tree_size_cur_++;
            result_tree_roots_[n->vid] = std::make_unique<ResultTreeNode>();
#ifdef MBE_ET13_DIAG
          ++et13_.v39_result_created_nodes;
#endif
          }
          r = result_tree_roots_[n->vid].get();
        } else {
          r = EnsureResultChild(r, n->vid);
        }
      } else {
        ++stats_.tg_batch_elided_result_visits;
      }
      for (auto &[id,c] : n->children) {
        // end_count is exact for the current Find state. Children without any
        // terminal path cannot contribute to sub_cnt or to a deferred output.
        // The skip-placeholder path has no need to materialize them.
        if (sparse && c->end_count == 0) continue;
        self(self, r, c.get());
      }
    };
    walk(walk, r_parent, block);
  }

  void dfs_find(ResultTreeNode *r_node, NeighborTreeNode *node, size_t depth) {
    if (config_.tg_batch_mode && node->end_count >= config_.tg_batch_min_ends &&
        TGBlockFullyDeferred(node)) {
      TGProcessDeferredBlock(r_node, node, depth);
      return;
    }
#ifdef MBE_ET13_DIAG
    ++et13_.dfs_find_calls;
    if (node->is_end) {
      ++et13_.dfs_end_paths;
      et13_.dfs_subcnt_ancestor_updates += depth;
    }
#endif
#ifdef MBE_V31_FORK_PATH
    v31_find_path_.push_back(node);
#endif
#ifdef MBE_V29_PROFILE
    ++v29_dfs_find_calls_;
    v29_dfs_find_end_paths_ += node->is_end;
#endif
#ifdef MBETM
    if (node->is_use)
#endif
    {
      auto watch = DebugTimer<12>::AutoWatch();

      if (r_node == nullptr) {
        if (!result_tree_roots_[node->vid]) {
          result_tree_size_cur_++;
          result_tree_roots_[node->vid] = std::make_unique<ResultTreeNode>();
#ifdef MBE_ET13_DIAG
          ++et13_.v39_result_created_nodes;
#endif
        }
        r_node = result_tree_roots_[node->vid].get();
      } else {
        r_node = EnsureResultChild(r_node, node->vid);
      }
    }

    if (node->is_end) {
      {
        auto watch = DebugTimer<13>::AutoWatch();

        // Even a TG-deferred end path must contribute to sub_cnt.  Later
        // (suffix) paths use these counts/jump links to build intersections
        // with all earlier canonical candidates.
        for (auto *s_node = node; s_node != nullptr; s_node = s_node->parent) s_node->sub_cnt++;
      }
      if (!node->tg_deferred &&
#ifdef MBETM
          node->is_res &&
#endif
          !r_node->is_end) {
        r_node->is_end = true;

#ifdef ONLY_COUNTING
        bic_cnt_++;
        if (bic_cnt_ % 1000000 == 0) {
          std::cout << "[DBG] cnt=" << bic_cnt_ << " time=" << main_watch_.Stop() << std::endl;

          std::ifstream status("/proc/self/status");
          for (std::string line; std::getline(status, line);) {
            if (line.rfind("VmPeak:", 0) == 0) {
              std::cout << " [MEMORY] VmPeak: " << std::stod(line.substr(7)) / 1024.0 << "MB" << std::endl;
            }
            if (line.rfind("VmSize:", 0) == 0) {
              std::cout << " [MEMORY] VmSize: " << std::stod(line.substr(7)) / 1024.0 << "MB" << std::endl;
            }
            if (line.rfind("VmHWM:", 0) == 0) {
              std::cout << " [MEMORY] VmHWM: " << std::stod(line.substr(6)) / 1024.0 << "MB" << std::endl;
            }
            if (line.rfind("VmRSS:", 0) == 0) {
              std::cout << " [MEMORY] VmRSS: " << std::stod(line.substr(6)) / 1024.0 << "MB" << std::endl;
            }
          }

          std::cout << " [STAT] duplicated_cnt=" << duplicated_cnt_ << std::endl;
          std::cout << " [STAT] cand_tree_size_cur=" << cand_tree_size_cur_ << std::endl;
          std::cout << " [STAT] cand_tree_size_max=" << cand_tree_size_max_ << std::endl;
          std::cout << " [STAT] cand_tree_size_total=" << cand_tree_size_total_ << std::endl;
          std::cout << " [STAT] result_tree_size_cur=" << result_tree_size_cur_ << std::endl;
          std::cout << " [STAT] result_tree_size_max=" << result_tree_size_max_ << std::endl;
          std::cout << " [STAT] result_tree_size_total=" << result_tree_size_total_ << std::endl;
        }
#endif

        // V56-D: if no vertex of the current terminal path has a prior
        // occurrence in this Find preorder, no predecessor path can contribute
        // to Fork. The self-copy is subsequently removed, so this Fork would
        // create an empty candidate tree. Skip only this proven-empty case.
        bool v56_empty_fork=false;
        if(config_.v56_prefork) {
          v56_empty_fork=true;
          for(const NeighborTreeNode *a=node;a;a=a->parent) {
            if(a->prev || a->sub_cnt!=node->sub_cnt) {v56_empty_fork=false;break;}
          }
        }
        if(v56_empty_fork) {++stats_.v56_pre_fork_skips;}
        else {
#ifdef MBE_V29_PROFILE
        ++v29_fork_calls_;
        v29_fork_depth_sum_ += depth;
        v29_fork_depth_max_ = std::max<uint64_t>(v29_fork_depth_max_, depth);
#endif
#ifdef MBE_ET13_DIAG
        ++et13_.fork_calls;
#endif
        size_t nbr_tree_size = 1;
        auto nbr_tree_root = std::make_unique<NeighborTreeNode>(-1, nullptr);

        {
#ifdef MBE_V52_INLINE_FORK_SCRATCH
          static constexpr size_t V52InlineCapacity = 24;
#endif
#ifdef MBE_V31_FORK_PATH
          // The nested Find() calls have their own path suffix; the active
          // suffix for this Find() always has precisely `depth` ancestors.
          V31PathView stack{v31_find_path_, v31_find_path_.size() - depth, depth};
          v31_fork_path_steps_reused_ += depth;
#elif defined(MBE_V52_INLINE_FORK_SCRATCH)
          // V52: avoid a heap allocation for each short Fork ancestor path.
          // Stack slots are overwritten before being read. For large depths
          // use the exact same logical array backed by std::vector.
          std::array<NeighborTreeNode *, V52InlineCapacity> fork_stack_inline;
          std::vector<NeighborTreeNode *> fork_stack_overflow;
          if (depth > V52InlineCapacity) fork_stack_overflow.resize(depth);
          // A non-owning slice preserves the original vector's back(),
          // range-for, and indexed access semantics without allocations.
          struct V52ForkSlice {
            NeighborTreeNode **p;
            size_t len;
            NeighborTreeNode *&operator[](size_t i) const { return p[i]; }
            NeighborTreeNode *&back() const { return p[len - 1]; }
            NeighborTreeNode **begin() const { return p; }
            NeighborTreeNode **end() const { return p + len; }
          };
          V52ForkSlice stack{depth <= V52InlineCapacity
              ? fork_stack_inline.data() : fork_stack_overflow.data(), depth};
#ifdef MBE_ET13_DIAG
          if (depth <= V52InlineCapacity) ++et13_.v52_inline_forks;
          else ++et13_.v52_heap_fallback_forks;
#endif
#elif defined(MBE_V29_REUSE_STACK)
          if (fork_stack_scratch_.size() <= depth) fork_stack_scratch_.resize(depth + 1);
          auto &stack = fork_stack_scratch_[depth];
          stack.assign(depth, nullptr);
#else
          std::vector<NeighborTreeNode *> stack(depth, nullptr);
#endif
#ifndef MBE_V31_FORK_PATH
          {
            size_t d = depth;
            for (auto *s_node = node; s_node != nullptr; s_node = s_node->parent) {
              stack[--d] = s_node;
            }
          }
#endif
          {
            auto watch = DebugTimer<14>::AutoWatch();

#ifdef MBE_V52_INLINE_FORK_SCRATCH
            // Per-prefix cursors have identical lifetime and access ordering
            // to the original vector; use the same capacity as the Fork path.
            std::array<NeighborTreeNode *, V52InlineCapacity> fork_cursor_inline;
            std::vector<NeighborTreeNode *> fork_cursor_overflow;
            if (depth > V52InlineCapacity) fork_cursor_overflow.resize(depth);
            NeighborTreeNode **s_node_vec = depth <= V52InlineCapacity
                ? fork_cursor_inline.data() : fork_cursor_overflow.data();
#elif defined(MBE_V29_REUSE_PREV)
            if (fork_prev_scratch_.size() <= depth) fork_prev_scratch_.resize(depth + 1);
            auto &s_node_vec = fork_prev_scratch_[depth];
            s_node_vec.assign(depth, nullptr);
#else
            std::vector<NeighborTreeNode *> s_node_vec(depth, nullptr);
#endif
#ifdef MBE_V30_LAZY_CURSOR
            // Lazy cursor initialization: for each si, initialize a cursor
            // for prefix position sj only when the predecessor scan needs it.
            // A stamp avoids O(depth) clearing for every new si.
            std::vector<size_t> cursor_stamp(depth, 0);
#endif
            for (size_t si = 0; si < depth; si++) {
#if !defined(MBE_V30_LAZY_CURSOR)
#ifdef MBE_V30_SKIP_EMPTY_PREV
              // Prefix cursors are never used if this path has no predecessor.
              if (stack[si]->prev != nullptr) {
#endif
              for (size_t sj = 0; sj < si; sj++) {
                s_node_vec[sj] = stack[sj];
              }
#ifdef MBE_V30_SKIP_EMPTY_PREV
              }
#endif
#endif
              auto *s_node = stack[si];
              auto vid = s_node->vid;
              {
                nbr_tree_size++;
                auto child = std::make_unique<NeighborTreeNode>(vid, nullptr);
                s_node->fork = child.get();
                child->sub_cnt = s_node->sub_cnt;
                if (si == 0) {
                  nbr_tree_root->children.emplace(vid, std::move(child));
                } else {
                  child->parent = stack[si - 1]->fork;
                  stack[si - 1]->fork->children.emplace(vid, std::move(child));
                }
              }
              for (s_node = s_node->prev; s_node != nullptr; s_node = s_node->prev) {
#ifdef MBE_ET13_DIAG
                ++et13_.fork_prev_steps;
#endif
                bool flag = false;
                for (size_t tsj = si; tsj > 0; tsj--) {
                  size_t sj = tsj - 1;
#ifdef MBE_ET13_DIAG
                  ++et13_.fork_ancestor_probes;
#endif
#ifdef MBE_V30_LAZY_CURSOR
                  if (cursor_stamp[sj] != si + 1) {
                    cursor_stamp[sj] = si + 1;
                    s_node_vec[sj] = stack[sj];
                  }
#endif
                  while (s_node_vec[sj] != nullptr && s_node_vec[sj]->dfs_idx.first > s_node->dfs_idx.first)
                    s_node_vec[sj] = s_node_vec[sj]->prev;
                  if (s_node_vec[sj] == nullptr) continue;
                  if (s_node_vec[sj]->dfs_idx.second >= s_node->dfs_idx.first) {
                    flag = true;
                    auto *f_node = s_node_vec[sj]->fork;
#ifdef MBE_ET13_DIAG
                    ++et13_.fork_child_insert_attempts;
#endif
                    auto [it, res] = f_node->children.try_emplace(vid, nullptr);
                    if (res) {
                      nbr_tree_size++;
                      it->second = std::make_unique<NeighborTreeNode>(vid, f_node);
                    }
                    it->second->sub_cnt += s_node->sub_cnt;
                    s_node->fork = it->second.get();
                    break;
                  }
                }
                if (!flag) {
#ifdef MBE_ET13_DIAG
                  ++et13_.fork_child_insert_attempts;
#endif
                  auto [it, res] = nbr_tree_root->children.try_emplace(vid, nullptr);
                  if (res) {
                    nbr_tree_size++;
                    it->second = std::make_unique<NeighborTreeNode>(vid, nullptr);
                  }
                  it->second->sub_cnt += s_node->sub_cnt;
                  s_node->fork = it->second.get();
                }
              }
            }
#if !defined(MBE_V29_REUSE_PREV) && !defined(MBE_V30_NO_SHRINK) && !defined(MBE_V52_INLINE_FORK_SCRATCH)
            s_node_vec.clear();
            s_node_vec.shrink_to_fit();
#endif
          }

          {
            auto watch = DebugTimer<15>::AutoWatch();

            size_t same_cnt = stack.back()->fork->sub_cnt;
            for (const auto &s_node : stack) {
              s_node->fork->sub_cnt -= same_cnt;
            }
            for (size_t tsi = depth; tsi > 0; tsi--) {
              size_t si = tsi - 1;
              if (tsi == depth) {
                auto *n_node = stack[si]->fork;
                auto p_node = (si == 0) ? nbr_tree_root.get() : stack[si - 1]->fork;
                p_node->children.erase(n_node->vid);
                continue;
              }
              auto *n_node = stack[si]->fork;
              if (n_node->children.empty() && n_node->sub_cnt == 0) {
                auto p_node = (si == 0) ? nbr_tree_root.get() : stack[si - 1]->fork;
                p_node->children.erase(n_node->vid);
              }
            }
          }
#if !defined(MBE_V31_FORK_PATH) && !defined(MBE_V29_REUSE_STACK) && !defined(MBE_V30_NO_SHRINK) && !defined(MBE_V52_INLINE_FORK_SCRATCH)
          stack.clear();
          stack.shrink_to_fit();
#endif
        }

#ifdef MBE_ET13_DIAG
        et13_.fork_nodes_before_reduce += nbr_tree_size;
#endif
        cand_tree_size_total_ += nbr_tree_size;
        cand_tree_size_cur_ += nbr_tree_size;
        cand_tree_size_max_ = std::max(cand_tree_size_max_, cand_tree_size_cur_);

        if (!nbr_tree_root->children.empty()) {
          {
            auto watch = DebugTimer<16>::AutoWatch();

            dfs_reduce(nbr_tree_root.get());
          }
#ifdef MBE_ET13_DIAG
          auto count_nodes=[&](auto&& self,const NeighborTreeNode *n)->uint64_t {
            uint64_t v=1;
            for(const auto &[id,c]:n->children) v+=self(self,c.get());
            return v;
          };
          et13_.fork_remaining_nodes+=count_nodes(count_nodes,nbr_tree_root.get());
#endif
          Find(std::move(nbr_tree_root));
        }

        nbr_tree_root.reset();
        cand_tree_size_cur_ -= nbr_tree_size;
        } // V56-D normal Fork
      } else if (!node->tg_deferred) {
        duplicated_cnt_++;
      }
    }

    for (auto &[id, child] : node->children) dfs_find(r_node, child.get(), depth + 1);
#ifdef MBE_V31_FORK_PATH
    v31_find_path_.pop_back();
#endif
  }

  // V59 cheap terminal chooser: only maintained root summaries and root-child
  // counts. No input-row materialization, Result Tree mutation or output
  // filtering occurs here. Rejected/failed attempts retain exact DFS fallback.
  enum class V59Choice : uint8_t { DFS, Mask, ET1, ET2 };
  V59Choice SelectV59(NeighborTreeNode *root) const {
    const size_t mode=config_.v59_dispatch;
    if (!root || root->is_end || !config_.et || !config_.et_root_enabled)
      return V59Choice::DFS;
    const size_t n=root->end_count, mi=root->min_end_len, ma=root->max_end_len;
    if (!n || mi<2 || mi==std::numeric_limits<size_t>::max() || ma<mi)
      return V59Choice::DFS;
    const size_t spread=ma-mi;
    const size_t gate=config_.v59_work_gate;
    const bool work_ok = !gate || (ma && n >= (gate-1)/ma+1);
    const bool mask_ok = config_.v56_terminal==3 && n>=config_.v59_mask_min_paths &&
         n<=config_.v56_max_paths && ma<=config_.v56_max_cols+1 && work_ok;
    // ET1 exact necessary root-child and length conditions; root metadata
    // includes the dummy-root shift, which cancels out for spreads.
    bool matching_ok=n>=config_.et_min_paths && spread<=1 && n<=ma &&
         root->children.size()<=2;
    if (matching_ok && root->children.size()==2) {
      auto it=root->children.begin(); ++it;
      if (it->second->end_count>1) matching_ok=false;
    }
    bool et2_ok=n>=config_.et_min_paths &&
       n<=config_.v59_et2_max_paths && spread<=2 && n<=2*(ma+1)+1;
    if (et2_ok && root->children.size()>1) {
      auto it=root->children.begin(); ++it; size_t later=0;
      for(;it!=root->children.end();++it) {
        if(it->second->end_count>2-later){et2_ok=false;break;}
        later+=it->second->end_count;
      }
    }
    if (mode==1) return mask_ok ? V59Choice::Mask : V59Choice::DFS;
    if (mode==2) return matching_ok ? V59Choice::ET1 : V59Choice::DFS;
    if (mode==3) return et2_ok ? V59Choice::ET2 : V59Choice::DFS;
    if (mode==4) {
      if (matching_ok && n<=8) return V59Choice::ET1;
      if (mask_ok) return V59Choice::Mask;
      if (et2_ok) return V59Choice::ET2;
      return V59Choice::DFS;
    }
    if (mode==5) {
      if (mask_ok && n>=12 && spread<=3 && ma && n >= (191/ma)+1)
        return V59Choice::Mask;
      if (matching_ok && n<=6) return V59Choice::ET1;
      if (et2_ok && n<=6) return V59Choice::ET2;
      return V59Choice::DFS;
    }
    if (mode==6) {
      if (matching_ok && n<=8) return V59Choice::ET1;
      return mask_ok ? V59Choice::Mask : V59Choice::DFS;
    }
    return V59Choice::DFS;
  }

  bool TryV59Exclusive(NeighborTreeNode *root) {
    ++stats_.v59_dispatch_calls;
    const V59Choice choice=SelectV59(root);
    bool ok=false;
    switch(choice) {
      case V59Choice::DFS: ++stats_.v59_selected_dfs; return false;
      case V59Choice::Mask:
        ++stats_.v59_selected_mask;
        ok=TryV56Terminal(root);
        if(ok) ++stats_.v59_mask_hits;
        break;
      case V59Choice::ET1:
        ++stats_.v59_selected_et1;
        ok=TryMatchingTerminal(root);
        if(ok) ++stats_.v59_et1_hits;
        break;
      case V59Choice::ET2:
        ++stats_.v59_selected_et2;
        ok=TryTwoBiplexTerminal(root);
        if(ok) ++stats_.v59_et2_hits;
        break;
    }
    if(!ok) ++stats_.v59_solver_failed;
    // Exclusive means *no second ET attempt*. Original DFS is authoritative.
    return ok;
  }

  void Find(std::unique_ptr<NeighborTreeNode> &&nbr_tree_root) {
#ifdef MBE_ET13_DIAG
    ++et13_.find_calls;
#endif
    SharedTGHint shared_hint;
    if (config_.v59_dispatch && config_.kappa==2) {
      if (TryV59Exclusive(nbr_tree_root.get())) return;
    } else {
      if (TryV56Terminal(nbr_tree_root.get())) return;
      if (config_.v59_no_et2_fallback && config_.kappa==2 && config_.v56_terminal==3) {
        ++stats_.v59_legacy_et2_skipped;
      } else if (TryBiplexTerminal(nbr_tree_root.get(),
                          config_.et_tg_shared ? &shared_hint : nullptr)) return;
    }
#ifdef MBE_ET13_DIAG
    if (config_.v51_sample_period &&
        (++v51_find_sample_counter_ % config_.v51_sample_period)==0)
      V51ClassifyTerminalFamily(nbr_tree_root.get());
#endif
    // Only the plain, non-shared TG prefix policy is fused. All other
    // modes retain the prior V48 path to keep controls directly comparable.
    const bool fuse = !config_.tg2_prefix && config_.tg_preorder_fuse && config_.tg && config_.et &&
      config_.kappa>=1 && config_.kappa<=2 && !config_.et_tg_shared &&
      !config_.tg_early_shape_gate && config_.tg_probe_period==1 &&
      !config_.tg_follow_et_auto_pause;
    const bool sample=config_.tg_phase_sample_period &&
      (++tg_phase_find_calls_ % config_.tg_phase_sample_period)==0;
    using TGClock=std::chrono::steady_clock;
    const auto p0=sample?TGClock::now():TGClock::time_point{};
    TGPrefixPlan tg_plan;
    {
      auto watch=DebugTimer<11>::AutoWatch();
      cand_tree_cnt_++;
      dfs_cnt_=0;
      if (fuse) {
        ++stats_.tg_fused_states;
        TGPreorderBuilder builder(config_,stats_,tg_scratch_current_,
                                  tg_scratch_first_,tg_scratch_misses_,nbr_tree_root.get());
        for (auto &[id,child]:nbr_tree_root->children)
          dfs_pre_fused(child.get(),builder,1);
        tg_plan=builder.finish();
      } else {
        for (auto &[id,child]:nbr_tree_root->children) dfs_pre(child.get());
      }
    }
    const auto p1=sample?TGClock::now():TGClock::time_point{};
    if (!fuse && config_.tg && config_.et && (config_.kappa==1 || config_.kappa==2)) {
      bool admit=true;
      if (config_.tg_follow_et_auto_pause && et_auto_skipped_last_) {
        ++stats_.tg_et_pause_skip;
        admit=false;
      }
      if (admit && config_.tg_early_shape_gate) {
        size_t k=std::max<size_t>(2,config_.tg_prefix_min);
        const NeighborTreeNode *first=nullptr;
        for (const auto &[id,child]:nbr_tree_root->children) {
          if (child->end_count) {first=child.get();break;}
        }
        if (!first || first->end_count+1<k) {
          ++stats_.tg_shape_gate_reject;
          admit=false;
        }
      }
      if (admit && config_.tg_probe_period>1 &&
          (++tg_probe_counter_%config_.tg_probe_period)!=0) {
        ++stats_.tg_probe_skip;
        admit=false;
      }
      if (admit) {
        if (config_.et_tg_shared && shared_hint.plan.active) {
          ++stats_.shared_prefix_used;
          stats_.shared_paths_reused+=shared_hint.accepted;
          ++stats_.tg_gate_attempts;
          ++stats_.tg_metadata_passed;
          ++stats_.tg_length_passed;
          ++stats_.tg_partition_hits;
          stats_.tg_deferred_paths+=shared_hint.accepted;
          if (shared_hint.accepted==2) ++stats_.tg_prefix2_hits;
          else ++stats_.tg_prefix_ge3_hits;
          for (size_t i=0;i<shared_hint.accepted;i++)
            shared_hint.ends[i]->tg_deferred=true;
          shared_hint.plan.last_deferred_preorder=
            shared_hint.ends[shared_hint.accepted-1]->dfs_idx.first;
          tg_plan=std::move(shared_hint.plan);
        } else {
          if (config_.et_tg_shared) ++stats_.shared_tg_fallbacks;
          tg_plan=config_.tg2_prefix ? BuildTG2PrefixPlan(nbr_tree_root.get())
                                      : BuildTGPrefixPlan(nbr_tree_root.get());
        }
      }
    }
    const auto p2=sample?TGClock::now():TGClock::time_point{};
    if (sample) {
      ++stats_.tg_profile_samples;
      stats_.tg_preorder_ns+=std::chrono::duration_cast<std::chrono::nanoseconds>(p1-p0).count();
      stats_.tg_planning_ns+=std::chrono::duration_cast<std::chrono::nanoseconds>(p2-p1).count();
    }
#ifdef MBETM
    {
      auto watch = DebugTimer<17>::AutoWatch();

      for (auto &[id, child] : nbr_tree_root->children) {
        build_use(child.get(), 1, false);
      }
    }
#endif
    // Find() nests inside Fork(), so preserve the parent Find's active block
    // boundary before entering any recursive descendant Find().
    const size_t previous_batch_boundary = tg_batch_boundary_preorder_;
    tg_batch_boundary_preorder_ = (config_.tg_batch_mode && tg_plan.active)
                                     ? tg_plan.last_deferred_preorder : 0;
    for (auto &[id, child] : nbr_tree_root->children) dfs_find(nullptr, child.get(), 1);
    tg_batch_boundary_preorder_ = previous_batch_boundary;
#ifdef MBE_ET13_DIAG
    if (config_.et && config_.tg_batch_verify_counters) {
      auto check = [&](auto &&self, const NeighborTreeNode *n) -> void {
        ++et13_.v39_candidate_total_nodes;
        if (n->sub_cnt != n->end_count)
          throw std::logic_error("v39 invalid final candidate sub_cnt vs end_count");
        for (const auto &[key,c] : n->children) self(self, c.get());
      };
      for (const auto &[key,c] : nbr_tree_root->children) check(check, c.get());
    }
#endif

    // Process the terminal-compatible prefix *after* the obstruction suffix.
    // This prevents prefix outputs from claiming a result-tree path that a
    // suffix branch still needs as the canonical owner of mixed intersections.
    if (tg_plan.active) {
      if (tg_plan.two_biplex) ResolveTG2Prefix(tg_plan);
      else ResolveMatchingTerminal(tg_plan.universe, std::move(tg_plan.defects),
                                   tg_plan.has_full_row);
    }
    if (sample) stats_.tg_search_resolve_ns+=
      std::chrono::duration_cast<std::chrono::nanoseconds>(TGClock::now()-p2).count();
  }

  void dfs_result_tree(ResultTreeNode *node, vid_t vid, size_t parent_dfs_idx) {
#ifdef MBE_ET13_DIAG
    ++et13_.dfs_result_nodes;
#endif
    result_tree_size_++;
    if (init_inter_neighbors_[vid].first != result_tree_root_vid_) {
      auto watch = DebugTimer<21>::AutoWatch();

      init_inter_neighbors_[vid].first = result_tree_root_vid_;
      init_inter_neighbors_[vid].second.clear();
      auto &root_nbrs = bi_graph_.VertexV(result_tree_root_vid_)->neighbors;
      auto &nbrs = bi_graph_.VertexV(vid)->neighbors;
      if (root_nbrs.size() / NumBits + 1 < nbrs.size()) {
        auto nit = nbrs.begin();
        size_t idx = 0;
        size_t tmp = 0;
        for (size_t i = 0, j = 1; i < root_nbrs.size(); i++) {
          while (nit != nbrs.end() && (*nit)->vid < root_nbrs[i]->vid) nit++;
          if (nit == nbrs.end()) break;
          if ((*nit)->vid == root_nbrs[i]->vid) {
            tmp |= j;
          }
          if (j == HighestBit) {
            if (tmp != 0) {
              init_inter_neighbors_[vid].second.emplace_back(idx, tmp);
              tmp = 0;
            }
            idx++;
            j = 1;
          } else {
            j <<= 1;
          }
        }
        if (tmp != 0) {
          init_inter_neighbors_[vid].second.emplace_back(idx, tmp);
        }
      }
    }
    auto dfs_idx = ++dfs_cnt_;
    if (result_tree_prev_dfs_idx_[vid].first != result_tree_cnt_) {
      result_tree_prev_dfs_idx_[vid] = {result_tree_cnt_, 0};
    } else if (result_tree_prev_dfs_idx_[vid].second > parent_dfs_idx) {
      node->has_prev = true;
    }
    result_tree_prev_dfs_idx_[vid].second = dfs_idx;
    for (auto &[id, child] : node->children) {
      dfs_result_tree(child.get(), id, dfs_idx);
    }
  }

  // ST v13: one reusable compressed-intersection vector per active DFS depth.
  // deque expansion preserves references to earlier depth slots, which is
  // necessary because child recursion reads the parent intersection by ref.
  // Cache ownership / push-pop behavior remains identical to v12.
  bool Enumerate(ResultTreeNode *node, vid_t vid, const CompressedNeighbors &PL,
                 VidList &R, size_t depth) {
    R.emplace_back(vid);
#ifdef MBE_V42_FAST_REPORT
    if (v42_lower_hash_stack_.size() <= depth) v42_lower_hash_stack_.resize(depth+1);
    V42HashState state;
    if (depth == 0) {
      // An Enumerate call may start below the root with an existing R prefix.
      for (size_t i=0;i+1<R.size();++i)
        state.add(bi_graph_.VertexV(R[i])->label);
    } else {
      state = v42_lower_hash_stack_[depth-1];
    }
    state.add(bi_graph_.VertexV(vid)->label);
    v42_lower_hash_stack_[depth] = state;
#endif
    if (st_intersection_scratch_.size() <= depth)
      st_intersection_scratch_.resize(depth + 1);
    CompressedNeighbors &intersected_neighbors = st_intersection_scratch_[depth];
    intersected_neighbors.clear();
    bool parent_need_pop_cache = false;
    if (vid == result_tree_root_vid_) {
      if (node->is_end) {
#ifdef MBE_V42_FAST_REPORT
        ReportFastCompressed(PL, R, depth);
#else
        Report(PL, R);
#endif
      }
    } else {
      if (cache_inter_neighbors_[vid].empty() && init_inter_neighbors_[vid].second.empty()) {
        auto watch = DebugTimer<31>::AutoWatch();

        auto &root_nbrs = bi_graph_.VertexV(result_tree_root_vid_)->neighbors;
        auto &nbrs = bi_graph_.VertexV(vid)->neighbors;
        auto nit = nbrs.begin();
#ifdef MBE_V29_PROFILE
        v29_compressed_blocks_scanned_ += PL.size();
#endif
        for (auto [idx, cpn] : PL) {
          size_t tmp = 0;
          while (cpn > 0) {
            auto ctz = __builtin_ctzl(cpn);
            auto nbr_vid = root_nbrs[idx * NumBits + ctz]->vid;
            while (nit != nbrs.end() && (*nit)->vid < nbr_vid) nit++;
            if (nit == nbrs.end()) break;
            auto low_bit = cpn & (-cpn);
            if ((*nit)->vid == nbr_vid) {
              tmp |= low_bit;
            }
            cpn ^= low_bit;
          }
          if (tmp != 0) {
            intersected_neighbors.emplace_back(idx, tmp);
          }
          if (nit == nbrs.end()) break;
        }
      } else {
        auto watch = DebugTimer<32>::AutoWatch();

        auto &cnbrs = cache_inter_neighbors_[vid].empty() ? init_inter_neighbors_[vid].second
                                                          : cache_inter_neighbors_[vid].back();
        auto cnit = cnbrs.begin();
#ifdef MBE_V29_PROFILE
        v29_compressed_blocks_scanned_ += PL.size();
#endif
        for (const auto &[idx, cpn] : PL) {
          while (cnit != cnbrs.end() && cnit->first < idx) cnit++;
          if (cnit == cnbrs.end()) break;
          if (cnit->first == idx) {
            size_t tmp = cnit->second & cpn;
            if (tmp > 0) {
              intersected_neighbors.emplace_back(idx, tmp);
            }
          }
        }
      }

#ifdef MBE_V29_PROFILE
      v29_compressed_blocks_emitted_ += intersected_neighbors.size();
#endif
      if (node->is_end) {
#ifdef MBE_V42_FAST_REPORT
        ReportFastCompressed(intersected_neighbors, R, depth);
#else
        Report(intersected_neighbors, R);
#endif
      }

      if (node->has_prev) {
        auto watch = DebugTimer<33>::AutoWatch();

        parent_need_pop_cache = true;
        cache_inter_neighbors_[vid].emplace_back(std::move(intersected_neighbors));
      }
    }
    bool need_pop_cache = false;
    for (auto rit = node->children.rbegin(); rit != node->children.rend(); rit++) {
      if (Enumerate(rit->second.get(), rit->first,
                    (vid == result_tree_root_vid_)
                        ? PL
                        : ((node->has_prev) ? cache_inter_neighbors_[vid].back() : intersected_neighbors),
                    R, depth + 1)) {
        need_pop_cache = true;
      }
    }
    if (need_pop_cache) {
      auto watch = DebugTimer<34>::AutoWatch();

      for (auto &[id, child] : node->children) {
        if (child->has_prev) {
          cache_inter_neighbors_[id].pop_back();
        }
      }
    }
    R.pop_back();
    return parent_need_pop_cache;
  }

  // Allocated lazily only when TG reaches an exact check; retained across
  // states, reset on every check. Not used by the terminal resolver.
  ET2Scratch et2_scratch_;
  VidList et_scratch_cur_;
  VidList et_scratch_first_;
  VidList et_scratch_universe_;
  VidList et_scratch_defects_;
  std::vector<ResultTreeNode *> v57_mask_prefix_nodes_;
  std::vector<uint32_t> v57_seen_epochs_;
  uint32_t v57_epoch_=0;
  std::vector<uint32_t> v57_closure_scratch_;
  std::vector<uint32_t> v61_col_bits_scratch_;
  std::vector<vid_t> v61_flat_rows_scratch_,v61_row_scratch_;
  std::vector<size_t> v61_flat_offsets_scratch_;
  std::vector<unsigned char> et_scratch_misses_;
  VidList tg_scratch_current_;
  VidList tg_scratch_first_;
  std::vector<unsigned char> tg_scratch_misses_;

#ifdef MBE_V31_FORK_PATH
  std::vector<NeighborTreeNode *> v31_find_path_;
#endif
  uint64_t v31_fork_path_steps_reused_ = 0;
  uint64_t v31_result_hot_hits_ = 0;

#ifdef MBE_ET13_DIAG
  uint64_t v51_find_sample_counter_=0;
#endif
  MBETFastConfig config_;
  MBETFastStats stats_;
  std::ofstream checksum_out_;
  BiGraph bi_graph_;
  bool swap_vertices_;
  SteadyClockWatch main_watch_;

  size_t bic_cnt_;
  // This controller is deliberately local to an enumeration run.
  // Every probe is followed by standard DFS whenever ET is disabled.
  bool et_auto_skipped_last_ = false;
  size_t tg_phase_find_calls_ = 0;
  size_t tg_probe_counter_ = 0;
  size_t et_auto_find_calls_ = 0;
  size_t et_auto_pause_until_ = 0;
  size_t et_auto_base_checks_ = 0;
  size_t et_auto_base_new_ = 0;
  std::vector<std::unique_ptr<ResultTreeNode>> result_tree_roots_;

  std::vector<vid_t> traverse_order_u_;
  std::vector<vid_t> traverse_order_u_tmp_;
  std::vector<vid_t> traverse_order_nbr_cnt_;
  std::vector<std::vector<std::pair<size_t, size_t>>> traverse_order_v_range_;
  std::vector<size_t> traverse_order_v_range_begin_;
  std::vector<std::pair<vid_t, size_t>> traverse_order_v_range_idx_;
  size_t max_traverse_order_v_range_begin_;
  size_t traverse_order_u_pos_;

  size_t cand_tree_size_cur_;
  size_t cand_tree_size_max_;
  size_t cand_tree_size_total_;
  size_t result_tree_size_;
  size_t result_tree_size_cur_;
  size_t result_tree_size_max_;
  size_t result_tree_size_total_;

  size_t cand_tree_cnt_;
  size_t tg_batch_boundary_preorder_ = 0;
  std::vector<std::pair<size_t, NeighborTreeNode *>> cand_tree_prev_node_;
  std::vector<std::pair<size_t, size_t>> result_tree_prev_dfs_idx_;
  size_t result_tree_root_vid_;
  size_t result_tree_cnt_;
  // ST v13 reusable storage. Only used by the single-threaded result-tree
  // enumerator. Each depth owns a distinct buffer; deque growth does not
  // invalidate the CompressedNeighbors references passed to descendants.
#ifdef MBE_V29_REUSE_STACK
  std::deque<std::vector<NeighborTreeNode *>> fork_stack_scratch_;
#endif
#ifdef MBE_V29_REUSE_PREV
  std::deque<std::vector<NeighborTreeNode *>> fork_prev_scratch_;
#endif
#ifdef MBE_V29_PROFILE
  uint64_t v29_dfs_find_calls_ = 0;
  uint64_t v29_dfs_find_end_paths_ = 0;
  uint64_t v29_fork_calls_ = 0;
  uint64_t v29_fork_depth_sum_ = 0;
  uint64_t v29_fork_depth_max_ = 0;
  uint64_t v29_root_builds_ = 0;
  uint64_t v29_output_calls_ = 0;
  uint64_t v29_compressed_blocks_scanned_ = 0;
  uint64_t v29_compressed_blocks_emitted_ = 0;
#endif
  std::deque<CompressedNeighbors> st_intersection_scratch_;
  std::vector<std::list<CompressedNeighbors>> cache_inter_neighbors_;
  std::vector<std::pair<vid_t, CompressedNeighbors>> init_inter_neighbors_;
  size_t dfs_cnt_;
#ifdef MBE_ET13_DIAG
  ET13Diagnostics et13_;
#endif
  size_t duplicated_cnt_;
};