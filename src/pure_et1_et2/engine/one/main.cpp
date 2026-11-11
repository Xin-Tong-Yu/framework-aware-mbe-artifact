#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sstream>
#include <vector>
#include <unordered_map>
#include <memory>
#include <cmath>

#include "common/bigraph.hpp"
#include "common/timer.hpp"
#include "src/MBET.hpp"

struct Args {
  std::string file;
  bool st = true;
  bool et = false;
  bool tg = false;
  size_t kappa = 1;
  size_t et2_max_defects = 28;
  size_t et2_max_mis = 512;
  bool et2_reuse_buffers = false;
  bool et2_root_degree_gate = false;
  bool et2_trie_prefix_reuse = false;
  size_t et2_reuse_min_mis = 3;
  size_t v56_terminal=0, v56_min_paths=5, v56_max_paths=32, v56_max_cols=128, v56_max_bits=12, v56_component_cap=10;
  bool v56_prefork=false;
  bool v57_mask_direct=false, v57_mask_prefix=false, v57_mask_fast_closure=false;
  size_t v57_mask_output_factor=0;
  size_t v59_dispatch=0;
  bool v59_no_et2_fallback=false;
  size_t v59_work_gate=96;
  size_t v59_mask_min_paths=8;
  size_t v59_et2_max_paths=12;
  bool v61_fast_sort=false, v61_fast_emit=false, v61_flat_rows=false;
  bool v62_tree_mask=false, v62_mask_cursor=false;
  bool v60_lazy_mask=false, v60_root_gate=false;
  size_t v60_mask_risk_factor=0;
  size_t v58_min_path_work=0, v58_max_length_spread=0;
  size_t et_min_paths = 3;
  bool et_cardinality_gate = false;
  bool et_root_enabled = true;
  bool et_root_shape_gate = false;
  bool et_root_summary = false;
  bool et_root_summary_verify = false;
  bool et_reuse_scratch = false;
  size_t tg_min_family = 0;
  bool tg2_prefix = false;
  bool tg2_require_nonmatching = false;
  bool tg_preorder_fuse = false;
  size_t tg_phase_sample_period = 0;
  bool et_tg_shared = false;
  bool tg_cached_root_count = false;
  bool tg_early_shape_gate = false;
  size_t tg_probe_period = 1;
  bool tg_follow_et_auto_pause = false;
  size_t tg_prefix_min = 3;
  size_t tg_prefix_cap = 16;
  size_t tg_two_min_family = 3;
  unsigned tg_batch_mode = 0;
  size_t tg_batch_min_ends = 1;
  bool tg_batch_verify_counters = false;
  bool et_profit_auto = false;
  size_t et_auto_yield_pct = 3;
  size_t et_auto_window = 4096;
  size_t et_auto_pause = 262144;
  size_t v51_sample_period = 0;
  size_t v51_max_paths = 64;
  size_t v51_max_cols = 128;
  size_t min_left = 1;
  size_t min_right = 1;
  std::string orientation = "auto"; // auto => stable size heuristic; auto-et remains explicit diagnostic mode
  std::string emit_path;
  bool emit_stdout = false;
};

static bool ParseOnOff(const std::string &s) {
  if (s == "on" || s == "1" || s == "true") return true;
  if (s == "off" || s == "0" || s == "false") return false;
  throw std::runtime_error("expected on/off, got: " + s);
}

static void Usage(const char *prog) {
  std::cerr
      << "Usage: " << prog << " -f graph [--st on|off] [--et on|off] [--tg on|off]\n"
      << "       [--kappa 1|2] [-l N] [-r N] [--orientation auto|auto-size|auto-et|left-upper|right-upper]\n"
      << "       [--emit FILE|stdout]\n";
}

static Args ParseArgs(int argc, char **argv) {
  Args a;
  for (int i = 1; i < argc; ++i) {
    std::string x = argv[i];
    auto need = [&](const char *name) -> std::string {
      if (i + 1 >= argc) throw std::runtime_error(std::string("missing value for ") + name);
      return argv[++i];
    };
    if (x == "-f" || x == "--file") a.file = need(x.c_str());
    else if (x == "--st") a.st = ParseOnOff(need("--st"));
    else if (x == "--et") a.et = ParseOnOff(need("--et"));
    else if (x == "--tg") a.tg = ParseOnOff(need("--tg"));
    else if (x == "--no-st") a.st = false;
    else if (x == "--no-et") a.et = false;
    else if (x == "--no-tg") a.tg = false;
    else if (x == "--v51-sample-period") a.v51_sample_period = std::stoull(need("--v51-sample-period"));
    else if (x == "--v51-max-paths") a.v51_max_paths = std::stoull(need("--v51-max-paths"));
    else if (x == "--v51-max-cols") a.v51_max_cols = std::stoull(need("--v51-max-cols"));
    else if (x == "--kappa") a.kappa = std::stoull(need("--kappa"));
    else if (x == "--v56-terminal") a.v56_terminal=std::stoull(need("--v56-terminal"));
    else if (x == "--v56-min-paths") a.v56_min_paths=std::stoull(need("--v56-min-paths"));
    else if (x == "--v56-max-paths") a.v56_max_paths=std::stoull(need("--v56-max-paths"));
    else if (x == "--v56-max-cols") a.v56_max_cols=std::stoull(need("--v56-max-cols"));
    else if (x == "--v56-max-bits") a.v56_max_bits=std::stoull(need("--v56-max-bits"));
    else if (x == "--v56-component-cap") a.v56_component_cap=std::stoull(need("--v56-component-cap"));
    else if (x == "--v56-prefork") a.v56_prefork=ParseOnOff(need("--v56-prefork"));
    else if (x == "--v57-mask-direct") a.v57_mask_direct=ParseOnOff(need("--v57-mask-direct"));
    else if (x == "--v57-mask-prefix") a.v57_mask_prefix=ParseOnOff(need("--v57-mask-prefix"));
    else if (x == "--v57-mask-fast-closure") a.v57_mask_fast_closure=ParseOnOff(need("--v57-mask-fast-closure"));
    else if (x == "--v57-mask-output-factor") a.v57_mask_output_factor=std::stoull(need("--v57-mask-output-factor"));
    else if (x == "--v59-dispatch") a.v59_dispatch=std::stoull(need("--v59-dispatch"));
    else if (x == "--v59-no-et2-fallback") a.v59_no_et2_fallback=ParseOnOff(need("--v59-no-et2-fallback"));
    else if (x == "--v59-work-gate") a.v59_work_gate=std::stoull(need("--v59-work-gate"));
    else if (x == "--v59-mask-min-paths") a.v59_mask_min_paths=std::stoull(need("--v59-mask-min-paths"));
    else if (x == "--v59-et2-max-paths") a.v59_et2_max_paths=std::stoull(need("--v59-et2-max-paths"));
    else if (x == "--v62-mask-cursor") a.v62_mask_cursor=ParseOnOff(need("--v62-mask-cursor"));
    else if (x == "--v62-tree-mask") a.v62_tree_mask=ParseOnOff(need("--v62-tree-mask"));
    else if (x == "--v61-fast-sort") a.v61_fast_sort=ParseOnOff(need("--v61-fast-sort"));
    else if (x == "--v61-fast-emit") a.v61_fast_emit=ParseOnOff(need("--v61-fast-emit"));
    else if (x == "--v61-flat-rows") a.v61_flat_rows=ParseOnOff(need("--v61-flat-rows"));
    else if (x == "--v60-lazy-mask") a.v60_lazy_mask=ParseOnOff(need("--v60-lazy-mask"));
    else if (x == "--v60-root-gate") a.v60_root_gate=ParseOnOff(need("--v60-root-gate"));
    else if (x == "--v60-mask-risk-factor") a.v60_mask_risk_factor=std::stoull(need("--v60-mask-risk-factor"));
    else if (x == "--v58-min-path-work") a.v58_min_path_work=std::stoull(need("--v58-min-path-work"));
    else if (x == "--v58-max-length-spread") a.v58_max_length_spread=std::stoull(need("--v58-max-length-spread"));
    else if (x == "--et2-max-defects") a.et2_max_defects = std::stoull(need("--et2-max-defects"));
    else if (x == "--et2-max-mis") a.et2_max_mis = std::stoull(need("--et2-max-mis"));
    else if (x == "--et2-reuse-buffers") a.et2_reuse_buffers = ParseOnOff(need("--et2-reuse-buffers"));
    else if (x == "--et2-root-degree-gate") a.et2_root_degree_gate = ParseOnOff(need("--et2-root-degree-gate"));
    else if (x == "--et2-trie-prefix-reuse") a.et2_trie_prefix_reuse = ParseOnOff(need("--et2-trie-prefix-reuse"));
    else if (x == "--et2-reuse-min-mis") a.et2_reuse_min_mis = std::stoull(need("--et2-reuse-min-mis"));
    else if (x == "--et-min-paths") a.et_min_paths = std::stoull(need("--et-min-paths"));
    else if (x == "--et-cardinality-gate") a.et_cardinality_gate = ParseOnOff(need("--et-cardinality-gate"));
    else if (x == "--et-root") a.et_root_enabled = ParseOnOff(need("--et-root"));
    else if (x == "--et-root-shape-gate") a.et_root_shape_gate = ParseOnOff(need("--et-root-shape-gate"));
    else if (x == "--et-root-summary") a.et_root_summary = ParseOnOff(need("--et-root-summary"));
    else if (x == "--et-root-summary-verify") a.et_root_summary_verify = ParseOnOff(need("--et-root-summary-verify"));
    else if (x == "--et-reuse-scratch") a.et_reuse_scratch = ParseOnOff(need("--et-reuse-scratch"));
    else if (x == "--tg-early-shape-gate") a.tg_early_shape_gate = ParseOnOff(need("--tg-early-shape-gate"));
    else if (x == "--tg-probe-period") a.tg_probe_period = std::stoull(need("--tg-probe-period"));
    else if (x == "--tg-follow-et-auto-pause") a.tg_follow_et_auto_pause = ParseOnOff(need("--tg-follow-et-auto-pause"));
    else if (x == "--tg-min-family") a.tg_min_family = std::stoull(need("--tg-min-family"));
    else if (x == "--tg2-prefix") a.tg2_prefix = ParseOnOff(need("--tg2-prefix"));
    else if (x == "--tg2-require-nonmatching") a.tg2_require_nonmatching = ParseOnOff(need("--tg2-require-nonmatching"));
    else if (x == "--tg-preorder-fuse") a.tg_preorder_fuse = ParseOnOff(need("--tg-preorder-fuse"));
    else if (x == "--tg-phase-sample-period") a.tg_phase_sample_period = std::stoull(need("--tg-phase-sample-period"));
    else if (x == "--et-tg-shared") a.et_tg_shared = ParseOnOff(need("--et-tg-shared"));
    else if (x == "--tg-cached-root-count") a.tg_cached_root_count = ParseOnOff(need("--tg-cached-root-count"));
    else if (x == "--tg-prefix-min") a.tg_prefix_min = std::stoull(need("--tg-prefix-min"));
    else if (x == "--tg-prefix-cap") a.tg_prefix_cap = std::stoull(need("--tg-prefix-cap"));
    else if (x == "--tg-two-min-family") a.tg_two_min_family = std::stoull(need("--tg-two-min-family"));
    else if (x == "--tg-batch-mode") {
      const auto mode=need("--tg-batch-mode");
      if (mode=="off") a.tg_batch_mode=0;
      else if (mode=="count") a.tg_batch_mode=1;
      else if (mode=="skip") a.tg_batch_mode=2;
      else if (mode=="sparse") a.tg_batch_mode=3;
      else throw std::runtime_error("bad --tg-batch-mode: "+mode);
    }
    else if (x == "--tg-batch-min-ends") a.tg_batch_min_ends = std::stoull(need("--tg-batch-min-ends"));
    else if (x == "--tg-batch-verify") a.tg_batch_verify_counters = ParseOnOff(need("--tg-batch-verify"));
    else if (x == "--et-profit-auto") a.et_profit_auto = ParseOnOff(need("--et-profit-auto"));
    else if (x == "--et-auto-yield-pct") a.et_auto_yield_pct = std::stoull(need("--et-auto-yield-pct"));
    else if (x == "--et-auto-window") a.et_auto_window = std::stoull(need("--et-auto-window"));
    else if (x == "--et-auto-pause") a.et_auto_pause = std::stoull(need("--et-auto-pause"));
    else if (x == "-l") a.min_left = std::stoull(need("-l"));
    else if (x == "-r") a.min_right = std::stoull(need("-r"));
    else if (x == "--orientation") a.orientation = need("--orientation");
    else if (x == "--emit") {
      auto v = need("--emit");
      if (v == "stdout") a.emit_stdout = true;
      else a.emit_path = v;
    } else if (x == "-h" || x == "--help") {
      Usage(argv[0]); std::exit(0);
    } else {
      throw std::runtime_error("unknown option: " + x);
    }
  }
  if (a.file.empty()) throw std::runtime_error("-f/--file is required");
  if (a.orientation != "auto" && a.orientation != "auto-size" && a.orientation != "auto-et" &&
      a.orientation != "left-upper" && a.orientation != "right-upper")
    throw std::runtime_error("invalid --orientation");
  if (a.et_auto_yield_pct > 100 || !a.et_auto_window || !a.et_auto_pause)
    throw std::runtime_error("invalid ET auto parameters");
  if (a.tg_prefix_min < 2 || a.tg_prefix_min > 64 || a.tg_prefix_cap < 2 || a.tg_prefix_cap > 64 || a.tg_prefix_min > a.tg_prefix_cap)
    throw std::runtime_error("invalid TG prefix min/cap");
  if (a.tg_probe_period < 1 || a.tg_probe_period > 1024) throw std::runtime_error("--tg-probe-period must be 1..1024");
  if (a.tg2_prefix && (!a.et || !a.tg || a.kappa != 2 || a.et_tg_shared || a.tg_preorder_fuse))
    throw std::runtime_error("--tg2-prefix requires --et on --tg on --kappa 2 with shared/fuse off");
  if (a.tg_two_min_family < 3 || a.tg_two_min_family > 1000000000ULL)
    throw std::runtime_error("--tg-two-min-family must be between 3 and 1e9");
  if (a.tg_batch_min_ends<1 || a.tg_batch_min_ends>64) throw std::runtime_error("--tg-batch-min-ends must be 1..64");
  if (a.tg_batch_mode && (!a.et || !a.tg)) throw std::runtime_error("TG batch mode requires --tg on and --et on");
  if (a.et_tg_shared && (!a.et || !a.tg || !a.et_root_enabled))
    throw std::runtime_error("--et-tg-shared on requires ET+TG+ET-root on");
  if (a.et && (a.kappa != 1 && a.kappa != 2))
    throw std::runtime_error("MBET-Fast ET supports --kappa 1 or 2");
  if (a.v60_mask_risk_factor>64) throw std::runtime_error("v60-mask-risk-factor 0..64");
  if (a.v59_dispatch>6 || a.v59_mask_min_paths<2 || a.v59_mask_min_paths>128 ||
      a.v59_et2_max_paths<2 || a.v59_et2_max_paths>4096)
    throw std::runtime_error("invalid V59 dispatch parameters");
  if (a.v56_terminal>4 || a.v56_max_bits>20 || a.v56_component_cap<2 ||
      a.v56_min_paths<2 || a.v56_max_paths<a.v56_min_paths ||
      a.v56_max_cols<1 || a.v56_max_cols>100000)
    throw std::runtime_error("invalid V56 terminal limits");
  if (a.et2_max_defects < 1 || a.et2_max_defects > 30 ||
      a.et2_max_mis < 1 || a.et2_max_mis > 65536)
    throw std::runtime_error("--et2-max-defects must be 1..30; --et2-max-mis 1..65536");
  if (a.et2_reuse_min_mis < 2 || a.et2_reuse_min_mis > 65536)
    throw std::runtime_error("--et2-reuse-min-mis must be between 2 and 65536");
  return a;
}


static double TerminalFriendlinessScore(const std::vector<std::shared_ptr<Vertex>> &upper,
                                        size_t sample_cap = 512) {
  if (upper.empty()) return 0.0;
  const size_t step = std::max<size_t>(1, upper.size() / std::max<size_t>(1, sample_cap));
  double score = 0.0;
  size_t sampled = 0;
  std::unordered_map<vid_t, size_t> inter;
  for (size_t ui = 0; ui < upper.size() && sampled < sample_cap; ui += step, ++sampled) {
    const auto &u = upper[ui];
    inter.clear();
    size_t wedges = 0;
    for (const auto &v : u->neighbors) {
      for (const auto &uu : v->neighbors) {
        if (uu.get() == u.get()) continue;
        ++inter[uu->vid];
        if (++wedges > 200000) break; // bound probe cost on very dense inputs
      }
      if (wedges > 200000) break;
    }
    if (inter.empty()) { score += 1.0; continue; }
    size_t good = 0;
    for (const auto &[id, cnt] : inter) {
      if (u->neighbors.size() <= cnt + 1) ++good;
    }
    // A terminal candidate needs both near-complete overlapping rows and a
    // small conflicting row population; the latter reduces collisions in the
    // missing-edge matching condition.
    const double frac_good = static_cast<double>(good) / static_cast<double>(inter.size());
    score += frac_good / std::sqrt(1.0 + static_cast<double>(inter.size()));
  }
  return sampled ? score / static_cast<double>(sampled) : 0.0;
}

int main(int argc, char **argv) {
  try {
    auto args = ParseArgs(argc, argv);

    auto load_watch = MainTimer::StopWatch();
    auto graph = BiGraph::LoadFromFile(args.file);
    double load_sec = load_watch.Stop();

    std::string resolved_orientation = args.orientation;
    double tg_score_left = -1.0, tg_score_right = -1.0;
    double tg_prep_sec = 0.0;
    if (resolved_orientation == "auto") resolved_orientation = "auto-size";
    if (resolved_orientation == "auto-size") {
      resolved_orientation = (graph.VerticesU().size() <= graph.VerticesV().size())
                               ? "left-upper" : "right-upper";
    } else if (resolved_orientation == "auto-et") {
      SteadyClockWatch tg_watch;
      tg_watch.Start();
      tg_score_left = TerminalFriendlinessScore(graph.VerticesU());
      tg_score_right = TerminalFriendlinessScore(graph.VerticesV());
      tg_prep_sec = tg_watch.Stop();
      if (tg_score_left == tg_score_right) {
        resolved_orientation = (graph.VerticesU().size() <= graph.VerticesV().size())
                                 ? "left-upper" : "right-upper";
      } else {
        resolved_orientation = tg_score_right > tg_score_left ? "right-upper" : "left-upper";
      }
    }

    bool swapped = false;
    if (resolved_orientation == "right-upper") {
      std::swap(graph.VerticesU(), graph.VerticesV());
      swapped = true;
    }

    MBETFastConfig cfg;
    cfg.st = args.st;
    cfg.et = args.et;
    cfg.tg = args.tg;
    cfg.kappa = args.kappa;
    cfg.v56_terminal=args.v56_terminal;
    cfg.v56_min_paths=args.v56_min_paths;
    cfg.v56_max_paths=args.v56_max_paths;
    cfg.v56_max_cols=args.v56_max_cols;
    cfg.v56_max_bits=args.v56_max_bits;
    cfg.v56_component_cap=args.v56_component_cap;
    cfg.v56_prefork=args.v56_prefork;
    cfg.v57_mask_direct=args.v57_mask_direct || args.v57_mask_prefix;
    cfg.v57_mask_prefix=args.v57_mask_prefix;
    cfg.v57_mask_fast_closure=args.v57_mask_fast_closure;
    cfg.v57_mask_output_factor=args.v57_mask_output_factor;
    cfg.v59_dispatch=args.v59_dispatch;
    cfg.v59_no_et2_fallback=args.v59_no_et2_fallback;
    cfg.v59_work_gate=args.v59_work_gate;
    cfg.v59_mask_min_paths=args.v59_mask_min_paths;
    cfg.v59_et2_max_paths=args.v59_et2_max_paths;
    cfg.v62_tree_mask=args.v62_tree_mask;
    cfg.v62_mask_cursor=args.v62_mask_cursor;
    cfg.v61_fast_sort=args.v61_fast_sort;
    cfg.v61_fast_emit=args.v61_fast_emit;
    cfg.v61_flat_rows=args.v61_flat_rows;
    cfg.v60_lazy_mask=args.v60_lazy_mask;
    cfg.v60_root_gate=args.v60_root_gate;
    cfg.v60_mask_risk_factor=args.v60_mask_risk_factor;
    cfg.v58_min_path_work=args.v58_min_path_work;
    cfg.v58_max_length_spread=args.v58_max_length_spread;
    cfg.et2_max_defects = args.et2_max_defects;
    cfg.et2_max_mis = args.et2_max_mis;
    cfg.et2_reuse_buffers = args.et2_reuse_buffers;
    cfg.et2_root_degree_gate = args.et2_root_degree_gate;
    cfg.et2_trie_prefix_reuse = args.et2_trie_prefix_reuse;
    cfg.et2_reuse_min_mis = args.et2_reuse_min_mis;
    cfg.v51_sample_period = args.v51_sample_period;
    cfg.v51_max_paths = args.v51_max_paths;
    cfg.v51_max_cols = args.v51_max_cols;
    cfg.et_min_paths = std::max<size_t>(2, args.et_min_paths);
    cfg.et_cardinality_gate = args.et_cardinality_gate;
    cfg.et_root_enabled = args.et_root_enabled;
    cfg.et_root_shape_gate = args.et_root_shape_gate;
    cfg.et_root_summary = args.et_root_summary;
    cfg.et_root_summary_verify = args.et_root_summary_verify;
    cfg.et_reuse_scratch = args.et_reuse_scratch;
    cfg.tg_min_family = args.tg_min_family;
    cfg.tg2_prefix = args.tg2_prefix;
    cfg.tg2_require_nonmatching = args.tg2_require_nonmatching;
    cfg.tg_preorder_fuse = args.tg_preorder_fuse;
    cfg.tg_phase_sample_period = args.tg_phase_sample_period;
    cfg.et_tg_shared = args.et_tg_shared;
    cfg.tg_cached_root_count = args.tg_cached_root_count;
    cfg.tg_early_shape_gate = args.tg_early_shape_gate;
    cfg.tg_probe_period = args.tg_probe_period;
    cfg.tg_follow_et_auto_pause = args.tg_follow_et_auto_pause;
    cfg.tg_prefix_min = args.tg_prefix_min;
    cfg.tg_prefix_cap = args.tg_prefix_cap;
    cfg.tg_two_min_family = args.tg_two_min_family;
    cfg.tg_batch_mode = args.tg_batch_mode;
    cfg.tg_batch_min_ends = args.tg_batch_min_ends;
    cfg.tg_batch_verify_counters = args.tg_batch_verify_counters;
    cfg.et_profit_auto = args.et_profit_auto;
    cfg.et_auto_yield_pct = args.et_auto_yield_pct;
    cfg.et_auto_window = args.et_auto_window;
    cfg.et_auto_pause = args.et_auto_pause;
    cfg.min_left = args.min_left;
    cfg.min_right = args.min_right;
    cfg.input_swapped = swapped;
    cfg.emit_stdout = args.emit_stdout;
    cfg.emit_path = args.emit_path;

    MBETFast engine(std::move(graph), cfg);
    auto [count, total_sec, times] = engine.Run();
    const auto &st = engine.Stats();
    double search_sec = times.count("run") ? times.at("run") : total_sec;
    double prep_sec = 0.0;
    if (times.count("sort")) prep_sec += times.at("sort");
    if (times.count("order")) prep_sec += times.at("order");

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "Algorithm: MBET-Fast\n";
    std::cout << "Modules: ST=" << (args.st ? "on" : "off")
              << " ET=" << (args.et ? "on" : "off")
              << " TG=" << (args.tg ? "on" : "off") << "\n";
    std::cout << "Orientation: " << resolved_orientation << "\n";
    if (tg_score_left >= 0.0) {
      std::cout << "TG_Score_LeftUpper: " << tg_score_left << "\n";
      std::cout << "TG_Score_RightUpper: " << tg_score_right << "\n";
    }
    std::cout << "Count: " << count << "\n";
    std::cout << "Checksum_XOR: " << st.checksum_xor << "\n";
    std::cout << "Checksum_SUM: " << st.checksum_sum << "\n";
    std::cout << "ET_Root: " << (args.et_root_enabled ? "on" : "off") << "\n";
    std::cout << "ET_Root_Summary: " << (args.et_root_summary ? "on" : "off") << "\n";
    std::cout << "ET_Root_Shape_Gate: " << (args.et_root_shape_gate ? "on" : "off") << "\n";
    std::cout << "ET_Root_Gate_Rejections: " << st.et_root_gate_reject << "\n";
    std::cout << "ET_Scratch_Reuse: " << (args.et_reuse_scratch ? "on" : "off") << "\n";
    std::cout << "ET_Scratch_Attempts: " << st.et_scratch_attempts << "\n";
    std::cout << "TG_Min_Family: " << args.tg_min_family << "\n";
    std::cout << "TG_Early_Shape_Gate: " << (args.tg_early_shape_gate ? "on" : "off") << "\n";
    std::cout << "TG_Early_Shape_Rejections: " << st.tg_shape_gate_reject << "\n";
    std::cout << "TG_Probe_Period: " << args.tg_probe_period << "\n";
    std::cout << "TG_Probe_Skips: " << st.tg_probe_skip << "\n";
    std::cout << "TG_ET_Pause_Skips: " << st.tg_et_pause_skip << "\n";
    std::cout << "TG_Family_Gate_Skips: " << st.tg_family_gate_skips << "\n";
    std::cout << "ET_Cardinality_Gate: " << (args.et_cardinality_gate ? "on" : "off") << "\n";
    std::cout << "ET_Auto: " << (args.et_profit_auto ? "on" : "off") << "\n";
    std::cout << "ET_Auto_Yield_Pct: " << args.et_auto_yield_pct << "\n";
    std::cout << "ET_Auto_Skipped_Calls: " << st.et_auto_skipped_calls << "\n";
    std::cout << "ET_Auto_Pauses: " << st.et_auto_pauses << "\n";
    std::cout << "ET_Auto_Probes: " << st.et_auto_probes << "\n";
    std::cout << "ET_Checks: " << st.et_checks << "\n";
    std::cout << "ET_Hits: " << st.et_hits << "\n";
    std::cout << "V56_Method: " << args.v56_terminal << "\n";
    std::cout << "V56_Attempts: " << st.v56_attempts << "\n";
    std::cout << "V56_Shape_Checked: " << st.v56_shape_checked << "\n";
    std::cout << "V56_Hits: " << st.v56_hits << "\n";
    std::cout << "V56_Outputs: " << st.v56_outputs << "\n";
    std::cout << "V56_Cap_Rejections: " << st.v56_cap_reject << "\n";
    std::cout << "V56_PreFork_Skips: " << st.v56_pre_fork_skips << "\n";
    std::cout << "V56_Pivot_Branches: " << st.v56_pivot_branches << "\n";
    std::cout << "V57_Mask_Closed: " << st.v57_mask_closed << "\n";
    std::cout << "V57_Mask_Candidates: " << st.v57_mask_candidates << "\n";
    std::cout << "V57_Mask_Output_Rejections: " << st.v57_mask_output_reject << "\n";
    std::cout << "V57_Mask_Direct_Outputs: " << st.v57_mask_direct_outputs << "\n";
    std::cout << "V57_Mask_Reused_Columns: " << st.v57_mask_reused_columns << "\n";
    std::cout << "V62_Tree_Mask_Nodes: " << st.v62_tree_mask_nodes << "\n";
    std::cout << "V62_Tree_Mask_Leaves: " << st.v62_tree_mask_leaves << "\n";
    std::cout << "V61_Fast_Sort_Batches: " << st.v61_fast_sort_batches << "\n";
    std::cout << "V61_Fast_Emit_Batches: " << st.v61_fast_emit_batches << "\n";
    std::cout << "V61_Flat_Rows_Captured: " << st.v61_flat_rows_captured << "\n";
    std::cout << "V60_Lazy_Mask: " << args.v60_lazy_mask << "\n";
    std::cout << "V60_Root_Gate: " << args.v60_root_gate << "\n";
    std::cout << "V60_Mask_Risk_Factor: " << args.v60_mask_risk_factor << "\n";
    std::cout << "V60_Root_Rejected: " << st.v60_root_reject << "\n";
    std::cout << "V60_Early_Rejected: " << st.v60_early_reject << "\n";
    std::cout << "V60_Probe_Success: " << st.v60_probe_success << "\n";
    std::cout << "V60_Probe_Paths: " << st.v60_probe_paths << "\n";
    std::cout << "V60_Risk_Rejected: " << st.v60_risk_reject << "\n";
    std::cout << "V60_Lazy_Masks: " << st.v60_lazy_masks << "\n";
    std::cout << "V59_Dispatch: " << args.v59_dispatch << "\n";
    std::cout << "V59_No_ET2_Fallback: " << args.v59_no_et2_fallback << "\n";
    std::cout << "V59_Dispatch_Calls: " << st.v59_dispatch_calls << "\n";
    std::cout << "V59_Selected_DFS: " << st.v59_selected_dfs << "\n";
    std::cout << "V59_Selected_Mask: " << st.v59_selected_mask << "\n";
    std::cout << "V59_Selected_ET1: " << st.v59_selected_et1 << "\n";
    std::cout << "V59_Selected_ET2: " << st.v59_selected_et2 << "\n";
    std::cout << "V59_Mask_Hits: " << st.v59_mask_hits << "\n";
    std::cout << "V59_ET1_Hits: " << st.v59_et1_hits << "\n";
    std::cout << "V59_ET2_Hits: " << st.v59_et2_hits << "\n";
    std::cout << "V59_Solver_Failed: " << st.v59_solver_failed << "\n";
    std::cout << "V59_Legacy_ET2_Skipped: " << st.v59_legacy_et2_skipped << "\n";
    std::cout << "V58_Gate_Work_Rejected: " << st.v58_gate_work_reject << "\n";
    std::cout << "V58_Gate_Spread_Rejected: " << st.v58_gate_spread_reject << "\n";
#ifdef MBE_V58_COST_PROFILE
    std::cout << "V58_Profile_TotalNs: " << st.v58_total_ns << "\n";
    std::cout << "V58_Profile_ShapeNs: " << st.v58_shape_ns << "\n";
    std::cout << "V58_Profile_MaskPrepNs: " << st.v58_maskprep_ns << "\n";
    std::cout << "V58_Profile_ClosureNs: " << st.v58_closure_ns << "\n";
    std::cout << "V58_Profile_EmitNs: " << st.v58_emit_ns << "\n";
    std::cout << "V58_Profile_MaskPrepCalls: " << st.v58_mask_prep_calls << "\n";
    std::cout << "V58_Profile_ClosureCalls: " << st.v58_closure_calls << "\n";
    std::cout << "V58_Profile_EmitCalls: " << st.v58_emit_calls << "\n";
#endif
    std::cout << "ET2_Attempts: " << st.et2_attempts << "\n";
    std::cout << "ET2_Verified: " << st.et2_verified << "\n";
    std::cout << "ET2_Hits: " << st.et2_hits << "\n";
    std::cout << "ET2_Nonmatching_Hits: " << st.et2_nonmatching_hits << "\n";
    std::cout << "ET2_Fallback_Shape: " << st.et2_fallback_shape << "\n";
    std::cout << "ET2_Fallback_Degree: " << st.et2_fallback_degree << "\n";
    std::cout << "ET2_Fallback_Cap: " << st.et2_fallback_cap << "\n";
    std::cout << "ET2_MIS_Generated: " << st.et2_mis_generated << "\n";
    std::cout << "ET2_Scratch_Reused_Calls: " << st.et2_scratch_reused_calls << "\n";
    std::cout << "ET2_Root_Degree_Gate: " << (args.et2_root_degree_gate ? "on" : "off") << "\n";
    std::cout << "ET2_Root_Gate_Rejections: " << st.et2_root_gate_rejections << "\n";
    std::cout << "ET2_Trie_Prefix_Reuse: " << (args.et2_trie_prefix_reuse ? "on" : "off") << "\n";
    std::cout << "ET2_Trie_Reuse_Batches: " << st.et2_trie_reuse_batches << "\n";
    std::cout << "ET2_Trie_Reused_Columns: " << st.et2_trie_reused_columns << "\n";
    std::cout << "ET_Generated_Lower_Layers: " << st.et_generated_lower_layers << "\n";
    std::cout << "TG_Reordered_Nodes: " << st.tg_reordered_nodes << "\n";
    std::cout << "TG2_Prefix_Enabled: " << (args.tg2_prefix?"on":"off") << "\n";
    std::cout << "TG2_Plan_Attempts: " << st.tg2_plan_attempts << "\n";
    std::cout << "TG2_Candidate_Prefixes: " << st.tg2_candidate_prefixes << "\n";
    std::cout << "TG2_Prefix_Hits: " << st.tg2_prefix_hits << "\n";
    std::cout << "TG2_Nonmatching_Hits: " << st.tg2_nonmatching_hits << "\n";
    std::cout << "TG2_Deferred_Paths: " << st.tg2_deferred_paths << "\n";
    std::cout << "TG2_MIS_Outputs: " << st.tg2_mis_outputs << "\n";
    std::cout << "TG2_Cap_Rejections: " << st.tg2_cap_rejections << "\n";
    std::cout << "TG2_Emit_New: " << st.tg2_emit_new << "\n";
    std::cout << "TG2_Emit_Duplicate: " << st.tg2_emit_duplicate << "\n";
    std::cout << "TG_Prefix_Min: " << args.tg_prefix_min << "\n";
    std::cout << "TG_Prefix_Cap: " << args.tg_prefix_cap << "\n";
    std::cout << "TG_Prefix2_Hits: " << st.tg_prefix2_hits << "\n";
    std::cout << "TG_Two_Min_Family: " << args.tg_two_min_family << "\n";
    std::cout << "TG_Two_Small_Family_Skips: " << st.tg_two_small_family_skips << "\n";
#ifdef MBE_ET13_DIAG
    std::cout << "TG_Two_Hit_Family_Hist: ";
    for (auto x: st.tg_two_hit_family_hist) std::cout << x << ",";
    std::cout << "\n";
#endif
    std::cout << "TG_Prefix_Ge3_Hits: " << st.tg_prefix_ge3_hits << "\n";
    std::cout << "TG_Partition_Checks: " << st.tg_partition_checks << "\n";
    std::cout << "TG_Partition_Hits: " << st.tg_partition_hits << "\n";
    std::cout << "TG_Deferred_Paths: " << st.tg_deferred_paths << "\n";
    std::cout << "TG_Batch_Verify: " << (args.tg_batch_verify_counters?"on":"off") << "\n";
    std::cout << "TG_Batch_Mode: " << (args.tg_batch_mode==0?"off":args.tg_batch_mode==1?"count":args.tg_batch_mode==2?"skip":"sparse") << "\n";
    std::cout << "TG_Batch_Min_Ends: " << args.tg_batch_min_ends << "\n";
    std::cout << "TG_Batch_Blocks: " << st.tg_batch_blocks << "\n";
    std::cout << "TG_Batch_Ends: " << st.tg_batch_ends << "\n";
    std::cout << "TG_Batch_Nodes: " << st.tg_batch_nodes << "\n";
    std::cout << "TG_Batch_Subcnt_Writes: " << st.tg_batch_subcnt_writes << "\n";
    std::cout << "TG_Batch_Saved_Internal_Updates: " << st.tg_batch_saved_internal_updates << "\n";
    std::cout << "TG_Batch_Saved_Ancestor_Updates: " << st.tg_batch_saved_ancestor_updates << "\n";
    std::cout << "TG_Batch_Elided_Result_Visits: " << st.tg_batch_elided_result_visits << "\n";
    std::cout << "TG_Batch_Singleton_Blocks: " << st.tg_batch_singletons << "\n";
    std::cout << "TG_Batch_Size_Hist: ";
    for (unsigned i=0;i<6;++i) std::cout << (i?",":"") << st.tg_batch_size_hist[i];
    std::cout << "\n";
    std::cout << "TG_Fused_States: " << st.tg_fused_states << "\n";
    std::cout << "TG_Fused_Terminal_Visits: " << st.tg_fused_terminal_visits << "\n";
    std::cout << "TG_Fused_Exact_Rows: " << st.tg_fused_exact_rows << "\n";
    std::cout << "TG_Fused_Length_Rejected: " << st.tg_fused_length_rejected << "\n";
    std::cout << "TG_Profile_Samples: " << st.tg_profile_samples << "\n";
    std::cout << "TG_Preorder_Sampled_ns: " << st.tg_preorder_ns << "\n";
    std::cout << "TG_Planning_Sampled_ns: " << st.tg_planning_ns << "\n";
    std::cout << "TG_SearchResolve_Sampled_ns: " << st.tg_search_resolve_ns << "\n";
    std::cout << "TG_Gate_Attempts: " << st.tg_gate_attempts << "\n";
    std::cout << "TG_Metadata_Passed: " << st.tg_metadata_passed << "\n";
    std::cout << "TG_Length_Passed: " << st.tg_length_passed << "\n";
    std::cout << "TG_Exact_Checks: " << st.tg_exact_checks << "\n";
    std::cout << "Shared_ET_Streams: " << st.shared_et_streams << "\n";
    std::cout << "Shared_Prefix_Candidates: " << st.shared_prefix_candidates << "\n";
    std::cout << "Shared_Prefix_Used: " << st.shared_prefix_used << "\n";
    std::cout << "Shared_Paths_Reused: " << st.shared_paths_reused << "\n";
    std::cout << "Shared_TG_Fallbacks: " << st.shared_tg_fallbacks << "\n";
    std::cout << "TG_Five_Path_Attempts: " << st.tg_five_path_attempts << "\n";
    std::cout << "TG_Five_Path_Hits: " << st.tg_five_path_hits << "\n";
    std::cout << "V31_Fork_Path_Steps_Reused: " << engine.ForkPathStepsReused() << "\n";
    std::cout << "V31_Result_Hot_Hits: " << engine.ResultHotHits() << "\n";
    std::cout << "Load_Time_ms: " << load_sec * 1000.0 << "\n";
    std::cout << "Preprocess_Time_ms: " << prep_sec * 1000.0 << "\n";
    std::cout << "TG_Preprocess_Time_ms: " << tg_prep_sec * 1000.0 << "\n";
#ifdef MBE_ET13_DIAG
    {
      const auto &d = engine.ETDiag();
      std::cout << "[V51] find=" << d.find_calls
                << " dfs_find=" << d.dfs_find_calls
                << " dfs_end=" << d.dfs_end_paths
                << " dfs_pre_nodes=" << d.dfs_pre_nodes
                << " dfs_reduce_nodes=" << d.dfs_reduce_nodes
                << " fork=" << d.fork_calls
                << " fork_nodes_created=" << d.fork_nodes_before_reduce
                << " fork_nodes_remaining=" << d.fork_remaining_nodes
                << " fork_prev_steps=" << d.fork_prev_steps
                << " fork_ancestor_probes=" << d.fork_ancestor_probes
                << " fork_child_attempts=" << d.fork_child_insert_attempts
                << " result_child_ensure=" << d.v39_result_ensure_calls
                << " result_nodes_created=" << d.v39_result_created_nodes
                << " dfs_result_nodes=" << d.dfs_result_nodes
                << " subcnt_ancestor_updates=" << d.dfs_subcnt_ancestor_updates
                << " sample_find=" << d.profile_samples
                << " sample_bounded=" << d.profile_sample_bounded
                << " sample_oversize_or_small=" << d.profile_sample_oversize
                << " sample_matching=" << d.profile_matching
                << " sample_one_exception=" << d.profile_one_exception
                << " sample_other=" << d.profile_other
                << " one_exception_family_hist=";
      for (unsigned i=0;i<5;++i) std::cout << (i?",":"") << d.profile_one_exception_family[i];
      std::cout << "\n";
      std::cout << "[V52] inline_forks=" << d.v52_inline_forks << " heap_fallback_forks=" << d.v52_heap_fallback_forks << "\n";
      std::cout << "[ET13] try=" << d.try_calls
                << " gate_few=" << d.gate_few_paths
                << " gate_length=" << d.gate_length
                << " gate_cardinality=" << d.gate_cardinality
                << " verified=" << d.verified
                << " reject_many=" << d.rejected_many_misses
                << " reject_collision=" << d.rejected_collision
                << " reject_pair=" << d.rejected_pair
                << " reject_empty_paths=" << d.rejected_empty_paths
                << " reject_empty_universe=" << d.rejected_empty_universe
                << " hit=" << d.successful
                << " terminal_paths_checked=" << d.terminal_paths_total
                << " matching_edges=" << d.matched_edges_total
                << " new_result_paths=" << d.new_result_paths
                << " duplicate_result_paths=" << d.duplicate_result_paths
                << " result_ensure=" << d.v39_result_ensure_calls
                << " result_new_nodes=" << d.v39_result_created_nodes
                << " candidate_final_verified=" << d.v39_candidate_total_nodes
                << " find_calls=" << d.find_calls
                << " dfs_find_calls=" << d.dfs_find_calls
                << " fork_calls=" << d.fork_calls
                << " eligible_ms=" << d.eligible_wall_ns / 1.e6
                << " resolve_ms=" << d.resolve_wall_ns / 1.e6
                << " collect_ms=" << d.collect_wall_ns / 1.e6
                << " matching_buckets=";
      for (int i=0;i<6;i++) std::cout << (i ? "," : "") << d.matching_size_buckets[i];
      std::cout << " path_buckets=";
      for (int i=0;i<5;i++) std::cout << (i ? "," : "") << d.verified_paths_buckets[i];
      std::cout << "\n";
    }
#endif
    std::cout << "Search_Time_ms: " << search_sec * 1000.0 << "\n";
    std::cout << "Total_Run_Time_ms: " << total_sec * 1000.0 << "\n";
    std::cout << "Approx_Wall_Time_ms: " << (load_sec + tg_prep_sec + total_sec) * 1000.0 << "\n";
    // Linux/WSL high-water resident memory, not virtual memory / VmPeak.
    std::ifstream proc_status("/proc/self/status");
    for (std::string line; std::getline(proc_status,line);) {
      if (line.rfind("VmHWM:",0)==0) {
        std::istringstream fields(line.substr(6));
        double kb=0; fields >> kb;
        std::cout << "Peak_RSS_MiB: " << (kb/1024.0) << "\n";
        break;
      }
    }
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "ERROR: " << e.what() << "\n";
    Usage(argv[0]);
    return 2;
  }
}
