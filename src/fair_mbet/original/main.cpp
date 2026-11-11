#include <iostream>
#include <iomanip>
#include <stdexcept>
#include <string>
#include "common/bigraph.hpp"
#include "common/timer.hpp"
#include "src/MBET.hpp"

int main(int argc,char**argv) {
 try {
   if(argc < 2) {std::cerr << "usage: binary graph.txt [--dump file.txt]\n";return 2;}
   const std::string path=argv[1];
   std::string dump;
   for(int i=2;i<argc;i++) {
     if(std::string(argv[i])=="--dump" && i+1<argc) dump=argv[++i];
     else {std::cerr<<"unknown argument: "<<argv[i]<<"\n";return 2;}
   }
   auto graph=BiGraph::LoadFromFile(path);
   const bool input_swapped = graph.VerticesU().size() > graph.VerticesV().size();
   if(input_swapped) std::swap(graph.VerticesU(),graph.VerticesV());
   MBET engine(std::move(graph),input_swapped);
   if(!dump.empty()) engine.SetFairDump(dump);
   auto [cnt,total,times]=engine.Run();
   const auto &f=engine.GetFairReporter();
   if(cnt != f.count) {std::cerr << "[ERROR] report count mismatch "<<cnt<<" vs "<<f.count<<"\n";return 5;}
   const double search=times.count("run") ? times.at("run") : -1;
   const double prep=times.count("sort") ? times.at("sort") : 0;
   const double order=times.count("order") ? times.at("order") : 0;
   std::cout<<std::fixed<<std::setprecision(9);
   std::cout<<"[FAIR_RESULT] mode="
#ifdef MBETM
       <<"mbetm"
#else
       <<"mbet"
#endif
       <<" count="<<cnt<<" checksum_xor="<<f.checksum_xor
       <<" checksum_sum="<<f.checksum_sum
       <<" search_s="<<search<<" order_s="<<order
       <<" presort_s="<<prep<<" engine_total_s="<<total<<"\n";
   return 0;
 }catch(const std::exception&e) {std::cerr<<"[FATAL] "<<e.what()<<"\n";return 1;}
}
