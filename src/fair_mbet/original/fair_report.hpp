#pragma once
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <stdexcept>
#include <string>
#include <vector>

// Identical to HashSide/HandleOutput in the uploaded MBET-Fast source.
// Report is invoked once per biclique (no disk tuples unless --dump was set).
struct FairReporter {
  uint64_t count = 0, checksum_xor = 0, checksum_sum = 0;
  std::ofstream dump;
  static uint64_t splitmix(uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
  }
  static uint64_t hash_side(const BiGraph& graph, const VidList& ids, bool upper) {
    uint64_t a = 0x243f6a8885a308d3ULL;
    uint64_t b = 0x13198a2e03707344ULL;
    for (auto id: ids) {
      const uint64_t label = upper ? graph.VertexU(id)->label : graph.VertexV(id)->label;
      const uint64_t h = splitmix(label + 0x100000001b3ULL);
      a += h;
      b ^= (h << (label & 31)) | (h >> ((64 - (label & 31)) & 63));
    }
    return splitmix(a ^ splitmix(b + ids.size()));
  }
  void set_dump(const std::string& name) {
    dump.open(name, std::ios::out | std::ios::trunc);
    if(!dump) throw std::runtime_error("cannot open output file: " + name);
  }
  void observe(const BiGraph& graph, const VidList& upper, const VidList& lower, bool swapped) {
    const uint64_t hu = hash_side(graph,upper,true);
    const uint64_t hl = hash_side(graph,lower,false);
    const uint64_t hleft = swapped ? hl : hu;
    const uint64_t hright = swapped ? hu : hl;
    const uint64_t hb = splitmix(splitmix(hleft + 0x6a09e667f3bcc909ULL) ^
                                 splitmix(hright + 0xbb67ae8584caa73bULL));
    ++count; checksum_xor ^= hb; checksum_sum += hb;
    if (dump) {
      auto emit = [&](const VidList& ids,bool u) {
        std::vector<uint64_t> values; values.reserve(ids.size());
        for(auto id:ids) values.push_back(u ? graph.VertexU(id)->label : graph.VertexV(id)->label);
        std::sort(values.begin(),values.end());
        dump << '[';
        for(size_t i=0;i<values.size();++i) { if(i) dump << ','; dump << values[i]; }
        dump << ']';
      };
      if(!swapped) { emit(upper,true);dump << '|';emit(lower,false); }
      else { emit(lower,false);dump << '|';emit(upper,true); }
      dump << '\n';
    }
  }
};
